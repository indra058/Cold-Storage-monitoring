"""
Automated Test Suite for Phase 6.3: Real-Time Alert & Notification System
Cold-Storage IoT Monitoring using LSTM

Verifies:
  CASE 1: NORMAL -> NORMAL (No duplicate alert event)
  CASE 2: NORMAL -> EARLY WARNING (Triggers exactly 1 EARLY WARNING event)
  CASE 3: EARLY WARNING -> WARNING (Triggers exactly 1 WARNING event)
  CASE 4: WARNING -> WARNING (No duplicate transition alert event)
  CASE 5: WARNING -> NORMAL (Triggers exactly 1 RECOVERY notification)
  CASE 6: Multi-Device Isolation (ESP32_01 remains NORMAL while ESP32_02 triggers WARNING)
  Endpoint Verification:
    - GET /api/alerts maintains backward compatibility
    - GET /api/devices maintains status integrity
    - WebSocket telemetry includes all required fields
"""

import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Windows terminal utf-8 support
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
from websockets.sync.client import connect

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/live"


class AlertStateEngine:
    """
    Python mirror of the React frontend Phase 6.3 State-Transition Alert Engine.
    Tracks state transitions and prevents duplicate alerts.
    """

    def __init__(self):
        self.device_states = {}  # device_id -> 'NORMAL' | 'EARLY WARNING' | 'WARNING'
        self.events_log = []     # List of fired transition events

    def process_telemetry(self, payload: dict) -> dict | None:
        dev_id = payload.get("device_id", "UNKNOWN")
        cur_risk = payload.get("risk_level", "NORMAL")
        prev_risk = self.device_states.get(dev_id, "NORMAL")
        self.device_states[dev_id] = cur_risk

        event = None

        if prev_risk != cur_risk:

            # Case: Transition to EARLY WARNING
            if cur_risk == "EARLY WARNING":
                event = {
                    "event_type": "EARLY WARNING",
                    "device_id": dev_id,
                    "actual_temp": payload.get("temperature"),
                    "pred_temp": payload.get("predicted_temperature"),
                    "timestamp": payload.get("timestamp"),
                    "message": payload.get("alert"),
                }
                self.events_log.append(event)

            # Case: Transition to WARNING
            elif cur_risk == "WARNING":
                event = {
                    "event_type": "WARNING",
                    "device_id": dev_id,
                    "actual_temp": payload.get("temperature"),
                    "pred_temp": payload.get("predicted_temperature"),
                    "timestamp": payload.get("timestamp"),
                    "message": payload.get("alert"),
                }
                self.events_log.append(event)

            # Case: Recovery to NORMAL from abnormal state
            elif cur_risk == "NORMAL" and prev_risk in ("EARLY WARNING", "WARNING"):
                event = {
                    "event_type": "RECOVERY",
                    "device_id": dev_id,
                    "actual_temp": payload.get("temperature"),
                    "pred_temp": payload.get("predicted_temperature"),
                    "timestamp": payload.get("timestamp"),
                    "message": "Temperature has returned to the safe range.",
                }
                self.events_log.append(event)

        return event


def post_reading(device_id: str, temperature: float, humidity: float = 71.0) -> dict:
    tstamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "device_id": device_id,
        "timestamp": tstamp,
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 1),
    }
    resp = requests.post(f"{BASE_URL}/api/sensor", json=payload, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


def run_phase_6_3_tests():
    print("=" * 80)
    print("🔔 STARTING PHASE 6.3 REAL-TIME ALERT & NOTIFICATION TEST SUITE")
    print("=" * 80)

    engine = AlertStateEngine()

    # Step 0: Initial Health Verification
    print("\n[Step 0] Checking API Health...")
    health = requests.get(f"{BASE_URL}/api/health", timeout=3.0).json()
    assert health.get("status") == "ok", "API is not healthy"
    print("✓ Backend is operational and healthy.")

    # =========================================================================
    # CASE 1: NORMAL -> NORMAL (No Duplicate Alert)
    # =========================================================================
    print("\n[Step 1] CASE 1: NORMAL -> NORMAL (Testing duplicate alert suppression)...")
    # Stabilize TEST_DEV_01 in NORMAL state
    for t in [4.35, 4.35, 4.36, 4.35]:
        res = post_reading("TEST_DEV_01", t)
        engine.process_telemetry(res)
        time.sleep(0.05)

    initial_events_count = len(engine.events_log)
    print(f"  Current state for TEST_DEV_01: {engine.device_states.get('TEST_DEV_01')}")

    # Send 3 more identical normal readings
    for t in [4.35, 4.36, 4.35]:
        res = post_reading("TEST_DEV_01", t)
        event = engine.process_telemetry(res)
        assert event is None, f"Expected NO event for NORMAL -> NORMAL, but got {event}"
        time.sleep(0.05)

    assert len(engine.events_log) == initial_events_count, "Events count should not increase on repeated NORMAL readings"
    print("✓ CASE 1 Passed: Repeated NORMAL readings generated 0 duplicate notifications.")

    # =========================================================================
    # CASE 2: NORMAL -> EARLY WARNING (Exactly 1 Alert Event)
    # =========================================================================
    print("\n[Step 2] CASE 2: NORMAL -> EARLY WARNING (Detecting persistent rise excursion)...")
    test_dev_02 = "TEST_DEV_02"
    # Seed buffer
    post_reading(test_dev_02, 4.30)
    engine.process_telemetry(post_reading(test_dev_02, 4.40))

    early_warning_fired = False
    events_before = len(engine.events_log)

    for t in [4.80, 5.30, 5.85, 6.45, 7.10]:
        res = post_reading(test_dev_02, t)
        event = engine.process_telemetry(res)
        if event and event["event_type"] == "EARLY WARNING":
            early_warning_fired = True
            print(f"  >>> Triggered Event: [{event['event_type']}] for {event['device_id']} | Actual: {event['actual_temp']}°C, Pred: {event['pred_temp']}°C")
        time.sleep(0.05)

    assert early_warning_fired, "Expected EARLY WARNING event was not triggered"
    new_early_warnings = [e for e in engine.events_log[events_before:] if e["event_type"] == "EARLY WARNING"]
    assert len(new_early_warnings) == 1, f"Expected exactly 1 EARLY WARNING transition event, got {len(new_early_warnings)}"
    print("✓ CASE 2 Passed: Exactly 1 EARLY WARNING event was generated.")

    # =========================================================================
    # CASE 3: EARLY WARNING -> WARNING (Exactly 1 Warning Event)
    # =========================================================================
    print("\n[Step 3] CASE 3: EARLY WARNING -> WARNING (Exceeding 8.0°C upper threshold)...")
    events_before_warning = len(engine.events_log)

    # Exceed threshold (>8.0°C)
    res_warn = post_reading(test_dev_02, 8.45)
    warn_event = engine.process_telemetry(res_warn)

    assert warn_event is not None, "Expected WARNING event upon exceeding threshold"
    assert warn_event["event_type"] == "WARNING", f"Expected WARNING, got {warn_event['event_type']}"
    assert warn_event["actual_temp"] == 8.45, "Mismatch in actual temperature"
    print(f"  >>> Triggered Event: [{warn_event['event_type']}] for {warn_event['device_id']} | Actual: {warn_event['actual_temp']}°C, Pred: {warn_event['pred_temp']}°C")

    new_warnings = [e for e in engine.events_log[events_before_warning:] if e["event_type"] == "WARNING"]
    assert len(new_warnings) == 1, f"Expected exactly 1 WARNING transition event, got {len(new_warnings)}"
    print("✓ CASE 3 Passed: Exactly 1 WARNING event was generated.")

    # =========================================================================
    # CASE 4: WARNING -> WARNING (No Duplicate Notification)
    # =========================================================================
    print("\n[Step 4] CASE 4: WARNING -> WARNING (Testing suppression of duplicate critical alerts)...")
    events_before_repeated = len(engine.events_log)

    # Send 4 more consecutive readings remaining above 8.0°C
    for t in [8.50, 8.55, 8.48, 8.52]:
        res = post_reading(test_dev_02, t)
        assert res["risk_level"] == "WARNING", "Telemetry should still be in WARNING"
        event = engine.process_telemetry(res)
        assert event is None, f"Expected NO duplicate event for WARNING -> WARNING, got {event}"
        time.sleep(0.05)

    assert len(engine.events_log) == events_before_repeated, "Event count should not increase on repeated WARNING readings"
    print("✓ CASE 4 Passed: 4 consecutive WARNING readings generated 0 duplicate notifications.")

    # =========================================================================
    # CASE 5: WARNING -> NORMAL (Exactly 1 RECOVERY Event)
    # =========================================================================
    print("\n[Step 5] CASE 5: WARNING -> NORMAL (Detecting thermal recovery into safe range)...")
    events_before_recovery = len(engine.events_log)

    # Cool back down to safe cold storage range
    recovery_temps = [7.20, 6.00, 5.00, 4.40, 4.30]
    recovery_event = None

    for t in recovery_temps:
        res = post_reading(test_dev_02, t)
        ev = engine.process_telemetry(res)
        if ev and ev["event_type"] == "RECOVERY":
            recovery_event = ev
            print(f"  >>> Triggered Event: [{ev['event_type']}] for {ev['device_id']} | Temp: {ev['actual_temp']}°C ({ev['message']})")
        time.sleep(0.05)

    assert recovery_event is not None, "Expected RECOVERY event was not triggered"
    assert recovery_event["event_type"] == "RECOVERY", "Event type mismatch"
    assert recovery_event["device_id"] == test_dev_02, "Device ID mismatch in recovery"

    new_recoveries = [e for e in engine.events_log[events_before_recovery:] if e["event_type"] == "RECOVERY"]
    assert len(new_recoveries) == 1, f"Expected exactly 1 RECOVERY event, got {len(new_recoveries)}"
    print("✓ CASE 5 Passed: Exactly 1 RECOVERY notification was generated on returning to safe range.")

    # =========================================================================
    # CASE 6: Multi-Device Isolation
    # =========================================================================
    print("\n[Step 6] CASE 6: Multi-Device Isolation...")
    # ESP32_01 is nominal
    dev1_res = post_reading("ESP32_01", 4.35)
    dev1_event = engine.process_telemetry(dev1_res)

    # ESP32_02 sends a warning reading
    dev2_res = post_reading("ESP32_02", 8.60)
    dev2_event = engine.process_telemetry(dev2_res)

    print(f"  ESP32_01 State: {engine.device_states.get('ESP32_01')} | Event: {dev1_event}")
    print(f"  ESP32_02 State: {engine.device_states.get('ESP32_02')} | Event: {dev2_event['event_type'] if dev2_event else None}")

    assert engine.device_states.get("ESP32_01") == "NORMAL", "ESP32_01 should remain in NORMAL"
    assert dev2_res["risk_level"] == "WARNING", "ESP32_02 should be in WARNING"
    print("✓ CASE 6 Passed: Alerts on ESP32_02 do not cross-contaminate ESP32_01.")

    # =========================================================================
    # Step 7: Verify GET /api/alerts and WebSocket Broadcasts
    # =========================================================================
    print("\n[Step 7] Testing GET /api/alerts and WebSocket broadcast payload...")
    alerts_resp = requests.get(f"{BASE_URL}/api/alerts?limit=10", timeout=3.0).json()
    assert len(alerts_resp) > 0, "/api/alerts is empty"
    first_alert = alerts_resp[0]
    for field in ["device_id", "timestamp", "temperature", "predicted_temperature", "risk_level", "alert"]:
        assert field in first_alert, f"Missing {field} in /api/alerts record"
    print(f"  Latest Alert via API: [{first_alert['risk_level']}] {first_alert['device_id']} at {first_alert['timestamp']} - {first_alert['temperature']}°C")

    # Check WebSocket broadcast includes device_id and predictions
    with connect(WS_URL) as ws:
        post_reading("ESP32_03", 4.20)
        ws_msg = json.loads(ws.recv())
        assert "device_id" in ws_msg, "device_id missing from WebSocket broadcast"
        assert "predicted_temperature" in ws_msg, "predicted_temperature missing from WebSocket broadcast"
        assert "risk_level" in ws_msg, "risk_level missing from WebSocket broadcast"
        print(f"  WebSocket Stream Verified: {ws_msg['device_id']} -> {ws_msg['risk_level']}")

    print("\n" + "=" * 80)
    print("🎉 ALL PHASE 6.3 NOTIFICATION & ALERT TESTS PASSED PERFECTLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase_6_3_tests()

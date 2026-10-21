"""
Automated Multi-Device Test Suite for Phase 6.2
Cold-Storage IoT Monitoring with LSTM

Tests:
  Case 1: ESP32_01 sends stable readings -> Expects NORMAL
  Case 2: ESP32_02 sends gradually increasing temperatures -> Expects EARLY WARNING
  Case 3: ESP32_03 sends readings exceeding 8.0°C -> Expects WARNING
  Case 4: Device cools back to safe range -> Expects NORMAL / Recovery
  API Verification:
    - /api/devices
    - /api/devices/{device_id}/history
    - /api/alerts
  WebSocket Verification:
    - Verifies device_id in /ws/live broadcast stream
  Data & Buffer Verification:
    - Verifies device-wise buffer separation
    - Verifies data/live_sensor_data.csv coexists records for all devices
"""

import sys
import time
import json
import csv
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
PROJECT_ROOT = Path(__file__).resolve().parent
LIVE_CSV_PATH = PROJECT_ROOT / "data" / "live_sensor_data.csv"


def post_telemetry(device_id: str, temperature: float, humidity: float = 70.0, timestamp: str = None) -> dict:
    tstamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "device_id": device_id,
        "timestamp": tstamp,
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 1),
    }
    resp = requests.post(f"{BASE_URL}/api/sensor", json=payload, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


def run_tests():
    print("=" * 80)
    print("🧪 STARTING PHASE 6.2 MULTI-DEVICE TEST SUITE")
    print("=" * 80)

    # 1. Test Health Endpoint
    print("\n[Step 1] Checking API Health...")
    health = requests.get(f"{BASE_URL}/api/health", timeout=3.0).json()
    print(f"Health Response: {health}")
    assert health.get("status") == "ok", "Health status is not ok"
    print("✓ Health check passed.")

    # 2. Case 1: ESP32_01 Stable Readings -> Expect NORMAL
    print("\n[Step 2] CASE 1: ESP32_01 sends stable nominal readings...")
    for t in [4.35, 4.35, 4.36, 4.35, 4.35, 4.36, 4.35, 4.35]:
        res1 = post_telemetry("ESP32_01", t, 71.2)
        print(f"  ESP32_01 | Temp: {res1['temperature']}°C | Pred: {res1['predicted_temperature']}°C | Trend: {res1['trend']} | Risk: {res1['risk_level']}")
        time.sleep(0.05)

    assert res1["risk_level"] == "NORMAL", f"Expected NORMAL for ESP32_01, got {res1['risk_level']}"
    assert res1["device_id"] == "ESP32_01", "Device ID mismatch"
    print("✓ CASE 1 Passed: ESP32_01 maintains NORMAL status.")

    # 3. Case 2: ESP32_02 Gradually Increases -> Expect EARLY WARNING
    print("\n[Step 3] CASE 2: ESP32_02 sends gradually increasing temperatures...")
    # Seed buffer first
    post_telemetry("ESP32_02", 4.40, 71.0)
    post_telemetry("ESP32_02", 4.50, 71.0)

    # Consecutive rises with delta >= 0.40°C
    rising_temps = [4.80, 5.25, 5.75, 6.30, 6.90]
    last_res2 = None
    early_warning_triggered = False

    for t in rising_temps:
        res2 = post_telemetry("ESP32_02", t, 70.0)
        print(f"  ESP32_02 | Temp: {res2['temperature']}°C | Pred: {res2['predicted_temperature']}°C | Trend: {res2['trend']} | Risk: {res2['risk_level']}")
        if res2["risk_level"] == "EARLY WARNING":
            early_warning_triggered = True
        last_res2 = res2
        time.sleep(0.1)

    assert early_warning_triggered, "Expected EARLY WARNING to be triggered for ESP32_02 rising trend"
    print("✓ CASE 2 Passed: ESP32_02 triggered EARLY WARNING on persistent rise.")

    # 4. Case 3: ESP32_03 Exceeds 8.0°C -> Expect WARNING
    print("\n[Step 4] CASE 3: ESP32_03 sends readings exceeding 8.0°C threshold...")
    # Send high temperature reading directly
    res3 = post_telemetry("ESP32_03", 8.45, 68.0)
    print(f"  ESP32_03 | Temp: {res3['temperature']}°C | Pred: {res3['predicted_temperature']}°C | Trend: {res3['trend']} | Risk: {res3['risk_level']}")
    assert res3["risk_level"] == "WARNING", f"Expected WARNING for ESP32_03 (>8°C), got {res3['risk_level']}"
    assert "exceeded" in res3["alert"].lower() or "exceeds" in res3["alert"].lower(), "Alert message should mention threshold violation"
    print("✓ CASE 3 Passed: ESP32_03 correctly triggered WARNING.")

    # 5. Case 4: Device cools back to safe range -> Expect NORMAL / Recovery
    print("\n[Step 5] CASE 4: ESP32_03 cools back down to safe cold-storage range...")
    cooling_temps = [7.50, 6.50, 5.50, 4.60, 4.30]
    last_res4 = None
    for t in cooling_temps:
        last_res4 = post_telemetry("ESP32_03", t, 72.0)
        print(f"  ESP32_03 (Cooling) | Temp: {last_res4['temperature']}°C | Pred: {last_res4['predicted_temperature']}°C | Trend: {last_res4['trend']} | Risk: {last_res4['risk_level']}")
        time.sleep(0.1)

    assert last_res4["risk_level"] == "NORMAL", f"Expected NORMAL after cooling, got {last_res4['risk_level']}"
    print("✓ CASE 4 Passed: Device successfully recovered to NORMAL status.")

    # 6. Verify Device Buffers Separation
    print("\n[Step 6] Verifying device-wise buffer separation...")
    # Read ESP32_01 again - it should STILL have nominal values, completely unaffected by ESP32_02 and ESP32_03
    res1_check = post_telemetry("ESP32_01", 4.35, 71.0)
    print(f"  ESP32_01 Check | Temp: {res1_check['temperature']}°C | Pred: {res1_check['predicted_temperature']}°C | Risk: {res1_check['risk_level']}")
    assert res1_check["risk_level"] == "NORMAL", "ESP32_01 should remain NORMAL and isolated"
    assert abs(res1_check["predicted_temperature"] - 4.35) < 1.0, "Prediction should be close to nominal, not contaminated by 8°C"
    print("✓ Buffer separation confirmed: Device readings do not contaminate each other.")

    # 7. Verify GET /api/devices
    print("\n[Step 7] Testing GET /api/devices...")
    devices_resp = requests.get(f"{BASE_URL}/api/devices", timeout=3.0)
    assert devices_resp.status_code == 200, f"/api/devices returned {devices_resp.status_code}"
    devices = devices_resp.json()
    print(f"Found {len(devices)} active devices:")
    device_ids = {d["device_id"] for d in devices}
    for d in devices:
        print(f"  - {d['device_id']}: {d['temperature']}°C, Pred: {d['predicted_temperature']}°C, Trend: {d['trend']}, Risk: {d['risk_level']}")

    assert "ESP32_01" in device_ids, "ESP32_01 missing from /api/devices"
    assert "ESP32_02" in device_ids, "ESP32_02 missing from /api/devices"
    assert "ESP32_03" in device_ids, "ESP32_03 missing from /api/devices"
    print("✓ /api/devices returns all 3 devices with complete metadata.")

    # 8. Verify GET /api/devices/{device_id}/history
    print("\n[Step 8] Testing GET /api/devices/{device_id}/history...")
    for dev_id in ["ESP32_01", "ESP32_02", "ESP32_03"]:
        hist_resp = requests.get(f"{BASE_URL}/api/devices/{dev_id}/history?limit=15", timeout=3.0)
        assert hist_resp.status_code == 200, f"History for {dev_id} returned {hist_resp.status_code}"
        history = hist_resp.json()
        print(f"  History for {dev_id}: {len(history)} records")
        assert len(history) > 0, f"History for {dev_id} is empty"
        # Check all records belong to dev_id
        for h in history:
            assert h["device_id"] == dev_id, f"History record has wrong device_id: {h['device_id']} vs {dev_id}"
            assert "temperature" in h and "predicted_temperature" in h, "Missing expected fields"
    print("✓ /api/devices/{device_id}/history successfully filters by device without mixing.")

    # 9. Verify GET /api/alerts
    print("\n[Step 9] Testing GET /api/alerts...")
    alerts_resp = requests.get(f"{BASE_URL}/api/alerts?limit=10", timeout=3.0)
    assert alerts_resp.status_code == 200, f"/api/alerts returned {alerts_resp.status_code}"
    alerts = alerts_resp.json()
    print(f"Recent active alerts count: {len(alerts)}")
    for a in alerts[:5]:
        print(f"  - [{a['risk_level']}] {a['device_id']} at {a['timestamp']}: {a['temperature']}°C ({a['alert']})")
    assert len(alerts) > 0, "Expected at least one active alert from test scenarios"
    assert any(a["risk_level"] in ("EARLY WARNING", "WARNING") for a in alerts), "Alerts should have EARLY WARNING or WARNING"
    print("✓ /api/alerts returns properly filtered abnormal risk records.")

    # 10. Verify WebSocket Stream Includes device_id
    print("\n[Step 10] Testing WebSocket /ws/live stream...")
    with connect(WS_URL) as ws:
        # Trigger a telemetry post while listening
        post_telemetry("ESP32_02", 5.10, 71.0)
        msg = ws.recv()
        ws_data = json.loads(msg)
        print(f"WebSocket received payload: {ws_data}")
        assert "device_id" in ws_data, "WebSocket payload must include device_id"
        assert "predicted_temperature" in ws_data, "WebSocket payload must include predicted_temperature"
    print("✓ WebSocket broadcast verification passed: payload contains device_id.")

    # 11. Verify CSV Storage
    print("\n[Step 11] Verifying data/live_sensor_data.csv coexistence...")
    assert LIVE_CSV_PATH.exists(), "live_sensor_data.csv does not exist"
    with open(LIVE_CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_devices = {row.get("Device_ID", "").strip() for row in reader}
    print(f"Unique Device_IDs present in live CSV: {csv_devices}")
    assert "ESP32_01" in csv_devices, "ESP32_01 missing in CSV"
    assert "ESP32_02" in csv_devices, "ESP32_02 missing in CSV"
    assert "ESP32_03" in csv_devices, "ESP32_03 missing in CSV"
    print("✓ CSV multi-device coexistence verified.")

    print("\n" + "=" * 80)
    print("🎉 ALL PHASE 6.2 TESTS PASSED PERFECTLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

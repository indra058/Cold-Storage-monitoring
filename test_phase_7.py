"""
Phase 7 Final Integration and End-to-End Validation Suite
Project: IoT-Based Cold-Storage Monitoring using LSTM

Verifies:
  1. Backend Health Endpoint
  2. Sensor Ingestion Endpoint
  3. LSTM Model Prediction & Inversion
  4. Risk & Trend Detection
  5. Multi-Device Buffer Isolation
  6. Device History Endpoint
  7. Alert System Endpoint
  8. WebSocket Broadcast Payload
  9. Normal State Transition
  10. Early Warning State Transition
  11. Warning State Transition
  12. Recovery State Detection & Event Generation
"""

import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Configure Windows terminal encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
from websockets.sync.client import connect

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/live"


def post_reading(device_id: str, temperature: float, humidity: float = 71.0) -> dict:
    """Posts telemetry reading to FastAPI backend."""
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


def run_phase_7_validation():
    print("=" * 80)
    print("🧪 EXECUTING PHASE 7 FINAL INTEGRATION & VALIDATION TEST SUITE")
    print("=" * 80)

    test_results = {}

    # 1. Backend Health Check
    try:
        health_resp = requests.get(f"{BASE_URL}/api/health", timeout=3.0)
        assert health_resp.status_code == 200, f"Status code {health_resp.status_code}"
        data = health_resp.json()
        assert data.get("status") == "ok", "Status is not ok"
        test_results["Backend health"] = True
        print("[PASS] 1. Backend health check passed.")
    except Exception as e:
        test_results["Backend health"] = False
        print(f"[FAIL] 1. Backend health check failed: {e}")

    # 2. Sensor Ingestion Endpoint
    try:
        ingest_res = post_reading("TEST_NODE_P7", 4.35, 71.5)
        assert ingest_res["device_id"] == "TEST_NODE_P7"
        assert "predicted_temperature" in ingest_res
        assert "risk_level" in ingest_res
        test_results["Sensor ingestion"] = True
        print("[PASS] 2. Sensor ingestion endpoint passed.")
    except Exception as e:
        test_results["Sensor ingestion"] = False
        print(f"[FAIL] 2. Sensor ingestion failed: {e}")

    # 3. LSTM Prediction Response
    try:
        pred_val = ingest_res.get("predicted_temperature")
        assert isinstance(pred_val, (int, float)), "Prediction is not numeric"
        # Prediction should be physically plausible for cold-storage
        assert 1.0 <= pred_val <= 12.0, f"Unrealistic LSTM prediction: {pred_val}"
        test_results["LSTM prediction"] = True
        print(f"[PASS] 3. LSTM prediction verified (Value: {pred_val:.2f}°C).")
    except Exception as e:
        test_results["LSTM prediction"] = False
        print(f"[FAIL] 3. LSTM prediction failed: {e}")

    # 4. Risk Detection (Threshold Rules & Trending)
    try:
        # High temperature threshold check
        high_res = post_reading("TEST_NODE_P7", 8.45)
        assert high_res["risk_level"] == "WARNING", f"Expected WARNING, got {high_res['risk_level']}"
        assert "exceeded" in high_res["alert"].lower() or "exceeds" in high_res["alert"].lower()
        test_results["Risk detection"] = True
        print("[PASS] 4. Risk detection threshold rules verified.")
    except Exception as e:
        test_results["Risk detection"] = False
        print(f"[FAIL] 4. Risk detection failed: {e}")

    # 5. Multi-Device Buffer Isolation
    try:
        # Send cold nominal reading for ESP32_01 and verify it does NOT see TEST_NODE_P7's 8.45°C
        dev1_res = post_reading("ESP32_01", 4.35)
        assert dev1_res["risk_level"] == "NORMAL", f"ESP32_01 should remain NORMAL, got {dev1_res['risk_level']}"
        assert abs(dev1_res["predicted_temperature"] - 4.35) < 1.5, "ESP32_01 contaminated by other device!"
        test_results["Multi-device isolation"] = True
        print("[PASS] 5. Multi-device buffer isolation confirmed.")
    except Exception as e:
        test_results["Multi-device isolation"] = False
        print(f"[FAIL] 5. Multi-device isolation failed: {e}")

    # 6. Device History API
    try:
        hist_resp = requests.get(f"{BASE_URL}/api/devices/ESP32_01/history?limit=10", timeout=3.0)
        assert hist_resp.status_code == 200
        records = hist_resp.json()
        assert len(records) > 0, "No history records returned"
        assert all(r["device_id"] == "ESP32_01" for r in records), "Device history contains mixed device IDs"
        test_results["Device history"] = True
        print(f"[PASS] 6. Device history API verified ({len(records)} records for ESP32_01).")
    except Exception as e:
        test_results["Device history"] = False
        print(f"[FAIL] 6. Device history API failed: {e}")

    # 7. Alert System Endpoint
    try:
        alert_resp = requests.get(f"{BASE_URL}/api/alerts?limit=10", timeout=3.0)
        assert alert_resp.status_code == 200
        alerts = alert_resp.json()
        assert len(alerts) > 0, "No alerts returned"
        assert any(a["risk_level"] in ("EARLY WARNING", "WARNING") for a in alerts)
        test_results["Alert system"] = True
        print(f"[PASS] 7. Alert system API verified ({len(alerts)} active/recent alerts).")
    except Exception as e:
        test_results["Alert system"] = False
        print(f"[FAIL] 7. Alert system API failed: {e}")

    # 8. WebSocket Telemetry Stream
    try:
        with connect(WS_URL) as ws:
            post_reading("ESP32_02", 5.20)
            msg = json.loads(ws.recv())
            assert "device_id" in msg, "device_id missing from WebSocket broadcast"
            assert "temperature" in msg, "temperature missing from WebSocket broadcast"
            assert "predicted_temperature" in msg, "predicted_temperature missing from WebSocket broadcast"
            assert "risk_level" in msg, "risk_level missing from WebSocket broadcast"
        test_results["WebSocket"] = True
        print(f"[PASS] 8. WebSocket broadcast verified ({msg['device_id']} | Temp: {msg['temperature']}°C).")
    except Exception as e:
        test_results["WebSocket"] = False
        print(f"[FAIL] 8. WebSocket failed: {e}")

    # 9. Recovery Detection & State Transitions (Cases 9, 10, 11, 12)
    try:
        recovery_dev = "TEST_RECOVERY_NODE"
        # Step A: Seed nominal buffer (NORMAL)
        for t in [4.30, 4.32, 4.35]:
            post_reading(recovery_dev, t)
            time.sleep(0.05)

        # Step B: Trigger EARLY WARNING via rising excursion
        early_warn_triggered = False
        for t in [4.80, 5.35, 5.95, 6.60, 7.20]:
            r = post_reading(recovery_dev, t)
            if r["risk_level"] == "EARLY WARNING":
                early_warn_triggered = True
            time.sleep(0.05)
        assert early_warn_triggered, "EARLY WARNING transition failed"

        # Step C: Trigger WARNING (>8.0°C)
        warn_r = post_reading(recovery_dev, 8.40)
        assert warn_r["risk_level"] == "WARNING", "WARNING transition failed"

        # Step D: Recover to safe range (NORMAL)
        recovered = False
        for t in [7.20, 6.10, 5.20, 4.50, 4.30]:
            rec_r = post_reading(recovery_dev, t)
            if rec_r["risk_level"] == "NORMAL":
                recovered = True
                break
            time.sleep(0.05)
        assert recovered, "RECOVERY to NORMAL transition failed"

        test_results["Recovery detection"] = True
        print("[PASS] 9-12. Full cycle (NORMAL -> EARLY WARNING -> WARNING -> RECOVERY) verified.")
    except Exception as e:
        test_results["Recovery detection"] = False
        print(f"[FAIL] 9-12. Recovery cycle failed: {e}")

    # Summary
    passed_count = sum(1 for v in test_results.values() if v)
    total_count = len(test_results)

    print("\n" + "=" * 50)
    print("PHASE 7 FINAL VALIDATION")
    print("=" * 50 + "\n")

    for test_name, status in test_results.items():
        tag = "[PASS]" if status else "[FAIL]"
        print(f"{tag} {test_name}")

    print(f"\nTOTAL: {passed_count}/{total_count} PASSED\n")

    if passed_count == total_count:
        print("PHASE 7 STATUS: READY FOR DEMONSTRATION")
    else:
        print("PHASE 7 STATUS: ISSUES DETECTED")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    run_phase_7_validation()

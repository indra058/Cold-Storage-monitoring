"""
Verification of Phase 6.1 ESP32 Simulator & Sensor API Test Cases

Tests:
CASE 1: Safe baseline (4.2°C - 4.6°C) -> Expected: NORMAL
CASE 2: Gradual warming (4.5 -> 4.8 -> 5.1 -> 5.5 -> 6.0 -> 6.5°C) -> Expected: EARLY WARNING
CASE 3: Threshold breach (> 8.0°C) -> Expected: WARNING
CASE 4: Recovery into safe band (< 5.0°C) -> Expected: RECOVERY / NORMAL
"""

import sys
import time
import json
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_URL = "http://127.0.0.1:8000/api/sensor"
DEVICE_ID = "ESP32_01"


def send_reading(temp: float, hum: float = 70.0, step_label: str = ""):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "device_id": DEVICE_ID,
        "timestamp": timestamp,
        "temperature": temp,
        "humidity": hum,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print(
            f"  {step_label:<10} | In: {temp:5.2f}°C | "
            f"Pred: {res['predicted_temperature']:5.2f}°C | "
            f"Trend: {res['trend']:<10} | "
            f"Risk: {res['risk_level']:<13} | "
            f"Alert: {res['alert']}"
        )
        return res


def run_tests():
    print("=" * 80)
    print("Executing Phase 6.1 ESP32 Sensor API Test Scenarios")
    print("=" * 80)

    # CASE 1: Temperature around 4-5°C (NORMAL)
    print("\n--- CASE 1: Stable Cold Storage (4°C - 5°C) ---")
    for t in [4.20, 4.25, 4.30, 4.28, 4.32]:
        res = send_reading(t, 71.5, "Case 1")
    assert res["risk_level"] == "NORMAL", f"Expected NORMAL, got {res['risk_level']}"
    print("  ✓ CASE 1 Passed: NORMAL confirmed.")

    # CASE 2: Gradual Warming (4.5 -> 4.8 -> 5.1 -> 5.5 -> 6.0 -> 6.5)
    print("\n--- CASE 2: Gradual Warming Excursion (4.5°C -> 6.5°C) ---")
    early_warning_seen = False
    for t in [4.50, 4.80, 5.10, 5.50, 6.00, 6.50]:
        res = send_reading(t, 69.0, "Case 2")
        if res["risk_level"] == "EARLY WARNING":
            early_warning_seen = True
    assert early_warning_seen, "Expected EARLY WARNING to trigger during persistent warming trend!"
    print("  ✓ CASE 2 Passed: EARLY WARNING confirmed on persistent rising slope.")

    # CASE 3: Temperature Exceeds 8°C (WARNING)
    print("\n--- CASE 3: Safety Limit Breach (> 8.0°C) ---")
    res = send_reading(8.35, 68.0, "Case 3")
    assert res["risk_level"] == "WARNING", f"Expected WARNING, got {res['risk_level']}"
    print("  ✓ CASE 3 Passed: WARNING confirmed on threshold breach.")

    # CASE 4: Temperature Decreases Back into Safe Range (RECOVERY / NORMAL)
    print("\n--- CASE 4: Refrigeration Recovery (8.0°C -> 4.5°C) ---")
    for t in [7.60, 6.80, 5.90, 5.20, 4.60, 4.30]:
        res = send_reading(t, 72.0, "Case 4")
    assert res["risk_level"] == "NORMAL", f"Expected NORMAL upon recovery, got {res['risk_level']}"
    print("  ✓ CASE 4 Passed: Recovery to NORMAL confirmed.")

    print("\n" + "=" * 80)
    print("ALL 4 TEST SCENARIOS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

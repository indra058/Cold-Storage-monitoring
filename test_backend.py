"""
Phase 5.1 Backend Verification Script

Tests:
1. REST health check at http://127.0.0.1:8000/api/health
2. Live WebSocket stream at ws://127.0.0.1:8000/ws/live
3. Verifies occurrence of NORMAL, EARLY WARNING, and WARNING risk states
"""

import sys
import json
import asyncio
import urllib.request
import websockets

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

HEALTH_URL = "http://127.0.0.1:8000/api/health"
WS_URL = "ws://127.0.0.1:8000/ws/live"


def test_health():
    print(f"[Testing REST] GET {HEALTH_URL}")
    req = urllib.request.Request(HEALTH_URL)
    with urllib.request.urlopen(req, timeout=5) as response:
        status_code = response.getcode()
        body = json.loads(response.read().decode())
        print(f"  Response ({status_code}): {body}")
        assert status_code == 200
        assert body.get("status") == "ok"
        print("  ✓ Health check passed!")


async def test_websocket(max_messages: int = 35):
    print(f"\n[Testing WebSocket] Connecting to {WS_URL} ...")
    states_observed = set()
    samples_by_state = {}

    async with websockets.connect(WS_URL) as ws:
        print("  ✓ Connected successfully! Receiving live telemetry stream...")

        for i in range(max_messages):
            msg_str = await ws.recv()
            data = json.loads(msg_str)
            r_level = data.get("risk_level")
            states_observed.add(r_level)

            if r_level not in samples_by_state:
                samples_by_state[r_level] = data

            print(
                f"  [{i+1:02d}] Temp: {data['temperature']:5.2f}°C | "
                f"Pred: {data['predicted_temperature']:5.2f}°C | "
                f"Trend: {data['trend']:<10} | "
                f"Risk: {r_level:<13} | "
                f"Alert: {data['alert'][:40]}..."
            )

            # If all 3 states have been observed, we can finish early
            if {"NORMAL", "EARLY WARNING", "WARNING"}.issubset(states_observed) and i >= 18:
                print("\n  ✓ All 3 risk states (NORMAL, EARLY WARNING, WARNING) successfully observed!")
                break

    print("\n--- Summary of Observed Risk States ---")
    for state, sample in samples_by_state.items():
        print(f"\nState: {state}")
        print(json.dumps(sample, indent=2))

    return samples_by_state


async def main():
    test_health()
    await test_websocket()


if __name__ == "__main__":
    asyncio.run(main())

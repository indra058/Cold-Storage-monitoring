"""
Multi-Device Software-Based ESP32 IoT Sensor Simulator (Phase 6.2)

Simulates multiple ESP32 microcontrollers with DHT22 / digital temperature-humidity
sensors deployed across different cold-storage storage zones / units:
  - ESP32_01: Stable nominal cold-storage (~4.2°C to 4.8°C)
  - ESP32_02: Occasional gradual warming excursions (triggers EARLY WARNING then WARNING, followed by cooling recovery)
  - ESP32_03: Normal thermostatic cooling duty cycles (~3.2°C to 5.2°C)

Sends telemetry JSON via HTTP POST to FastAPI /api/sensor:
{
    "device_id": "ESP32_01",
    "timestamp": "YYYY-MM-DD HH:MM:SS",
    "temperature": float,
    "humidity": float
}
"""

import sys
import time
import random
import argparse
from datetime import datetime

# Handle Windows terminal utf-8 output cleanly
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
except ImportError:
    import urllib.request
    import json
    requests = None

# Configuration defaults
DEFAULT_API_URL = "http://127.0.0.1:8000/api/sensor"
DEFAULT_DEVICES = ["ESP32_01", "ESP32_02", "ESP32_03"]
DEFAULT_INTERVAL = 1.8  # Seconds between transmission rounds


class VirtualESP32Device:
    """
    Simulates thermal physics and sensor telemetry for an individual ESP32 node.
    Supports specific thermal behavioral modes:
      - 'stable': Stays in nominal safe range (4.2°C - 4.8°C)
      - 'warming_excursion': Periodic gradual heating excursions (triggers EARLY WARNING & WARNING)
      - 'cooling_cycle': Standard refrigeration compressor cycling (3.2°C - 5.2°C)
    """

    def __init__(self, device_id: str, mode: str = "stable", initial_temp: float = 4.3, initial_humidity: float = 71.0):
        self.device_id = device_id
        self.mode = mode
        self.current_temp = initial_temp
        self.current_humidity = initial_humidity
        self.step_counter = 0

        # Internal state for warming excursions (ESP32_02)
        self.phase = "nominal"
        self.steps_until_excursion = 10 if mode == "warming_excursion" else 9999
        self.excursion_steps_left = 0
        self.recovery_steps_left = 0

        # Internal state for cooling cycles (ESP32_03)
        self.cycle_dir = "cooling" if mode == "cooling_cycle" else "none"

    def get_next_reading(self) -> dict:
        """Generates the next continuous, physically realistic temperature & humidity sample."""
        self.step_counter += 1

        if self.mode == "stable":
            # Stable baseline cold storage around 4.2°C - 4.8°C
            # Subtle random walk with mean reversion towards 4.45°C
            drift = (4.45 - self.current_temp) * 0.15
            step_change = drift + random.uniform(-0.06, 0.06)
            self.current_temp += step_change
            self.current_humidity += random.uniform(-0.15, 0.15)
            self.current_humidity = max(68.0, min(74.0, self.current_humidity))

        elif self.mode == "warming_excursion":
            # Occasional gradual warming excursion simulating door open / refrigeration malfunction
            self.steps_until_excursion -= 1

            if self.steps_until_excursion <= 0 and self.phase == "nominal":
                self.phase = "warming"
                self.excursion_steps_left = random.randint(7, 9)
                self.steps_until_excursion = random.randint(22, 28)

            if self.phase == "warming":
                # Gradual temperature increase (+0.42°C to +0.60°C per step)
                rise = round(random.uniform(0.42, 0.60), 2)
                self.current_temp += rise
                self.current_humidity -= round(random.uniform(0.1, 0.3), 1)
                self.excursion_steps_left -= 1

                if self.excursion_steps_left <= 0 or self.current_temp >= 8.5:
                    self.phase = "cooling_recovery"
                    self.recovery_steps_left = random.randint(8, 12)

            elif self.phase == "cooling_recovery":
                # Emergency cooling engages and brings temperature back down smoothly
                drop = round(random.uniform(0.42, 0.62), 2)
                self.current_temp -= drop
                self.current_humidity += round(random.uniform(0.1, 0.3), 1)
                self.recovery_steps_left -= 1

                if self.recovery_steps_left <= 0 or self.current_temp <= 4.3:
                    self.phase = "nominal"

            else:
                # Nominal operation between excursions (~4.3°C - 4.7°C)
                drift = (4.4 - self.current_temp) * 0.18
                self.current_temp += drift + random.uniform(-0.05, 0.05)
                self.current_humidity += random.uniform(-0.15, 0.15)

        elif self.mode == "cooling_cycle":
            # Normal periodic cooling and mild warm recovery cycle (3.2°C to 5.2°C)
            if self.cycle_dir == "cooling":
                self.current_temp -= round(random.uniform(0.12, 0.22), 2)
                self.current_humidity += round(random.uniform(-0.1, 0.2), 1)
                if self.current_temp <= 3.3:
                    self.cycle_dir = "warming"
            else:
                self.current_temp += round(random.uniform(0.10, 0.18), 2)
                self.current_humidity += round(random.uniform(-0.2, 0.1), 1)
                if self.current_temp >= 5.1:
                    self.cycle_dir = "cooling"

        # Subtle measurement noise
        self.current_temp += round(random.gauss(0, 0.015), 2)

        # Realistic safety clamping
        self.current_temp = max(2.1, min(10.2, round(self.current_temp, 2)))
        self.current_humidity = max(60.0, min(80.0, round(self.current_humidity, 1)))

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "device_id": self.device_id,
            "timestamp": timestamp_str,
            "temperature": round(self.current_temp, 2),
            "humidity": round(self.current_humidity, 1),
        }


class MultiDeviceESP32Simulator:
    """Manages telemetry generation and API posting for multiple virtual ESP32 nodes."""

    def __init__(self, api_url: str = DEFAULT_API_URL, devices: list[str] = None):
        self.api_url = api_url
        device_names = devices or DEFAULT_DEVICES

        self.devices: list[VirtualESP32Device] = []
        for dev in device_names:
            if dev == "ESP32_01":
                self.devices.append(VirtualESP32Device(dev, mode="stable", initial_temp=4.35, initial_humidity=71.5))
            elif dev == "ESP32_02":
                self.devices.append(VirtualESP32Device(dev, mode="warming_excursion", initial_temp=4.50, initial_humidity=70.0))
            elif dev == "ESP32_03":
                self.devices.append(VirtualESP32Device(dev, mode="cooling_cycle", initial_temp=3.80, initial_humidity=72.0))
            else:
                self.devices.append(VirtualESP32Device(dev, mode="stable", initial_temp=4.40, initial_humidity=71.0))

    def post_telemetry(self, payload: dict) -> dict:
        """Transmits JSON reading to FastAPI /api/sensor."""
        if requests is not None:
            resp = requests.post(self.api_url, json=payload, timeout=4.0)
            resp.raise_for_status()
            return resp.json()
        else:
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                return json.loads(resp.read().decode("utf-8"))

    def run(self, interval: float = DEFAULT_INTERVAL):
        """Continuously polls all configured devices and posts telemetry."""
        print("=" * 78)
        print("📡 Multi-Device ESP32 IoT Sensor Simulator (Phase 6.2)")
        print("=" * 78)
        print(f"Target URL   : {self.api_url}")
        print(f"Active Nodes : {', '.join([d.device_id + f' ({d.mode})' for d in self.devices])}")
        print(f"Interval     : {interval}s per round")
        print("Running continuously. Press Ctrl+C to terminate.\n")

        round_num = 0
        try:
            while True:
                round_num += 1
                for dev in self.devices:
                    payload = dev.get_next_reading()
                    try:
                        result = self.post_telemetry(payload)
                        print(
                            f"[{round_num:03d}] {payload['device_id']:<8} | "
                            f"{payload['timestamp'].split(' ')[1]} | "
                            f"Temp: {payload['temperature']:5.2f}°C | "
                            f"Hum: {payload['humidity']:4.1f}% | "
                            f"Pred: {result.get('predicted_temperature', 0.0):5.2f}°C | "
                            f"Trend: {result.get('trend', 'N/A'):<10} | "
                            f"Risk: {result.get('risk_level', 'N/A'):<13} | "
                            f"{result.get('alert', '')[:30]}..."
                        )
                    except Exception as err:
                        print(f"[{round_num:03d}] {payload['device_id']} Error: {err}")

                    # Micro-delay between devices in the same round for natural pacing
                    time.sleep(0.15)

                time.sleep(max(0.2, interval - (0.15 * len(self.devices))))

        except KeyboardInterrupt:
            print("\n[Simulator] Multi-device simulation stopped by user.")


def run_simulator(api_url: str = DEFAULT_API_URL, devices: list[str] = None, interval: float = DEFAULT_INTERVAL):
    """Entry point helper."""
    sim = MultiDeviceESP32Simulator(api_url=api_url, devices=devices)
    sim.run(interval=interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Device ESP32 Cold-Storage IoT Simulator (Phase 6.2)")
    parser.add_argument("--url", type=str, default=DEFAULT_API_URL, help=f"Backend API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--devices", type=str, default=",".join(DEFAULT_DEVICES), help="Comma-separated device IDs")
    parser.add_argument("--device", type=str, default=None, help="Single device ID override (backward compatibility)")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help=f"Interval between rounds (default: {DEFAULT_INTERVAL}s)")
    args = parser.parse_args()

    device_list = [args.device] if args.device else [d.strip() for d in args.devices.split(",") if d.strip()]
    run_simulator(api_url=args.url, devices=device_list, interval=args.interval)

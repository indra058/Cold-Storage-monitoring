"""
IoT-Based Cold-Storage Monitoring - Phase 1: Sensor Simulator

Simulates temperature and humidity sensor readings for cold-storage monitoring
when physical hardware (e.g., ESP32 + DHT22) is not available.
"""

import os
import sys
import csv
import time
import random
import argparse
from datetime import datetime

# Configure utf-8 encoding on standard output for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# --- Configuration Constants ---
DATA_DIR = "data"
CSV_FILE_PATH = os.path.join(DATA_DIR, "sensor_data.csv")

# Cold storage thresholds (standard chilled cold storage: 2°C to 8°C)
TEMP_MIN_NORMAL = 2.0
TEMP_MAX_NORMAL = 8.0
HUMIDITY_MIN_NORMAL = 60.0
HUMIDITY_MAX_NORMAL = 85.0


class ColdStorageSimulator:
    """
    Simulates cold storage temperature and humidity readings with realistic
    fluctuations and periodic anomaly/warning conditions.
    """

    def __init__(self, base_temp: float = 4.5, base_humidity: float = 72.0):
        self.current_temp = base_temp
        self.current_humidity = base_humidity
        self.anomaly_active = False
        self.step_counter = 0

    def generate_reading(self) -> dict:
        """
        Generates a single sensor reading.
        Incorporates small random fluctuations and occasional warming trends (anomalies).
        """
        self.step_counter += 1

        # Trigger anomaly periodically (e.g., every 8-12 readings, simulate door open or cooling failure)
        # In a short run, this guarantees both NORMAL and WARNING states are observed.
        if not self.anomaly_active and (self.step_counter % 7 == 0):
            self.anomaly_active = True
            self.anomaly_duration = random.randint(4, 6)
            self.anomaly_steps_left = self.anomaly_duration

        if self.anomaly_active:
            # Temperature rises gradually into WARNING range
            self.current_temp += round(random.uniform(0.7, 1.3), 2)
            # Humidity slightly drops or fluctuates during warming
            self.current_humidity += round(random.uniform(-1.5, 1.0), 1)
            self.anomaly_steps_left -= 1

            if self.anomaly_steps_left <= 0:
                self.anomaly_active = False
        else:
            # Normal operation: small fluctuations reverting toward nominal base (~4.5°C)
            if self.current_temp > 5.5:
                # Cooling kicks in
                self.current_temp -= round(random.uniform(0.3, 0.7), 2)
            elif self.current_temp < 3.0:
                self.current_temp += round(random.uniform(0.2, 0.5), 2)
            else:
                self.current_temp += round(random.uniform(-0.3, 0.3), 2)

            # Humidity normal fluctuations
            self.current_humidity += round(random.uniform(-0.8, 0.8), 1)

        # Keep values clamped within plausible physical bounds
        self.current_temp = max(-5.0, min(25.0, round(self.current_temp, 1)))
        self.current_humidity = max(30.0, min(95.0, round(self.current_humidity, 1)))

        # Determine status
        status = self.evaluate_status(self.current_temp, self.current_humidity)

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "Timestamp": timestamp_str,
            "Temperature": f"{self.current_temp:.1f}",
            "Humidity": f"{self.current_humidity:.1f}",
            "Status": status
        }

    @staticmethod
    def evaluate_status(temperature: float, humidity: float) -> str:
        """
        Evaluates storage safety status based on cold storage operating range.
        NORMAL: 2.0°C <= Temp <= 8.0°C and 60% <= Humidity <= 85%
        WARNING: Any breach outside safe operating thresholds.
        """
        if (TEMP_MIN_NORMAL <= temperature <= TEMP_MAX_NORMAL) and (
            HUMIDITY_MIN_NORMAL <= humidity <= HUMIDITY_MAX_NORMAL
        ):
            return "NORMAL"
        return "WARNING"


def init_storage(file_path: str = CSV_FILE_PATH):
    """Ensures directory exists and CSV file has a header."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Temperature", "Humidity", "Status"])


def append_reading_to_csv(reading: dict, file_path: str = CSV_FILE_PATH):
    """Appends a single reading to the CSV file."""
    with open(file_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            reading["Timestamp"],
            reading["Temperature"],
            reading["Humidity"],
            reading["Status"]
        ])


def display_reading(reading: dict):
    """Displays the latest reading in the requested terminal format."""
    print(f"Timestamp   : {reading['Timestamp']}")
    print(f"Temperature : {reading['Temperature']} °C")
    print(f"Humidity    : {reading['Humidity']} %")
    print(f"Status      : {reading['Status']}")
    print("-" * 35)


def run_simulation(interval: float = 1.0, max_samples: int = None):
    """
    Runs the simulation loop.
    :param interval: Delay in seconds between readings.
    :param max_samples: Maximum number of readings to generate (None for continuous).
    """
    init_storage(CSV_FILE_PATH)
    simulator = ColdStorageSimulator()

    print(f"=== Cold-Storage IoT Sensor Simulator (Phase 1) ===")
    print(f"Saving data to: {CSV_FILE_PATH}")
    print(f"Update interval: {interval}s")
    if max_samples:
        print(f"Running for {max_samples} samples...")
    else:
        print("Running continuously. Press Ctrl+C to stop.\n")

    count = 0
    try:
        while True:
            reading = simulator.generate_reading()
            append_reading_to_csv(reading, CSV_FILE_PATH)
            display_reading(reading)

            count += 1
            if max_samples and count >= max_samples:
                print(f"Completed {count} simulated readings.")
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simulated IoT Sensor Data Collection for Cold Storage (Phase 1)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Delay in seconds between sensor readings (default: 1.0s)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=None,
        help="Total number of samples to generate before exiting (default: infinite)",
    )
    args = parser.parse_args()

    run_simulation(interval=args.interval, max_samples=args.samples)

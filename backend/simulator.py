"""
Live IoT Cold-Storage Sensor Simulator (Phase 5.1)

Generates continuous, realistic cold-storage temperature and humidity telemetry
evolving sequentially from previous states. Simulates:
1. NORMAL operating cycles (3.2°C - 5.5°C)
2. Gradual RISING temperatures (warming excursions)
3. WARNING conditions (> 8.0°C)
4. Smooth refrigeration recovery back toward normal
"""

import time
import random
from datetime import datetime


class LiveSensorSimulator:
    """
    Simulates sequential IoT cold-storage sensor telemetry.
    Maintains continuous thermal dynamics without abrupt random jumps.
    """

    def __init__(self, initial_temp: float = 4.2, initial_humidity: float = 72.0):
        self.current_temp = initial_temp
        self.current_humidity = initial_humidity

        # Phase states: 'normal_cooling', 'normal_warming', 'anomaly_warming', 'anomaly_recovery'
        self.phase = "normal_warming"
        self.step_counter = 0

        # Anomaly schedule: every 20-25 steps trigger a warming event
        self.steps_until_next_anomaly = 14
        self.anomaly_steps_left = 0
        self.recovery_steps_left = 0

    def generate_reading(self) -> dict:
        """
        Generates the next real-time reading evolving from the current state.
        Returns a dictionary with timestamp, temperature, and humidity.
        """
        self.step_counter += 1
        self.steps_until_next_anomaly -= 1

        # Check if an anomaly should be initiated
        if self.steps_until_next_anomaly <= 0 and self.phase in ("normal_cooling", "normal_warming"):
            self.phase = "anomaly_warming"
            self.anomaly_steps_left = random.randint(7, 10)
            self.steps_until_next_anomaly = random.randint(22, 28)

        # State machine for thermal evolution
        if self.phase == "anomaly_warming":
            # Continuous upward climb into warning range (e.g., +0.40 to +0.65°C per step)
            rise = round(random.uniform(0.40, 0.65), 2)
            self.current_temp += rise
            self.current_humidity -= round(random.uniform(0.1, 0.4), 1)
            self.anomaly_steps_left -= 1

            if self.anomaly_steps_left <= 0 or self.current_temp >= 8.6:
                self.phase = "anomaly_recovery"
                self.recovery_steps_left = random.randint(9, 12)

        elif self.phase == "anomaly_recovery":
            # Active refrigeration pulls temperature back down
            drop = round(random.uniform(0.40, 0.60), 2)
            self.current_temp -= drop
            self.current_humidity += round(random.uniform(0.1, 0.3), 1)
            self.recovery_steps_left -= 1

            if self.recovery_steps_left <= 0 or self.current_temp <= 4.2:
                self.phase = "normal_cooling"

        elif self.phase == "normal_cooling":
            # Minor thermostatic cooling cycle
            drop = round(random.uniform(0.10, 0.20), 2)
            self.current_temp -= drop
            self.current_humidity += round(random.uniform(-0.2, 0.2), 1)

            if self.current_temp <= 3.4:
                self.phase = "normal_warming"

        elif self.phase == "normal_warming":
            # Minor ambient warm creep during compressor idle
            rise = round(random.uniform(0.08, 0.16), 2)
            self.current_temp += rise
            self.current_humidity += round(random.uniform(-0.2, 0.2), 1)

            if self.current_temp >= 5.6:
                self.phase = "normal_cooling"

        # Subtle Gaussian measurement noise
        self.current_temp += round(random.gauss(0, 0.02), 2)

        # Physical safety clamping
        self.current_temp = max(2.1, min(10.5, round(self.current_temp, 2)))
        self.current_humidity = max(55.0, min(85.0, round(self.current_humidity, 1)))

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "timestamp": timestamp_str,
            "temperature": round(self.current_temp, 2),
            "humidity": round(self.current_humidity, 1),
        }

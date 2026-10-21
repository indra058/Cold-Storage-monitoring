"""
IoT-Based Cold-Storage Monitoring - Phase 2.5: Modeling Dataset Generator

Generates a realistic, high-volume (1,200+ samples) cold-storage time-series dataset
for training LSTM temperature forecasting models.

Cold Storage Operating Characteristics:
- Target Operating Range: 2.0 °C to 8.0 °C (chilled storage standard)
- Nominal Baseline: ~4.0 °C to 4.5 °C
- Natural Thermostatic Cycling: Compressor cycles on at ~5.5 °C - 6.0 °C, cycles off at ~3.2 °C
- Periodic Real-World Excursions: Simulated door openings / loading / defrost delays
  causing gradual warming to 8.5 °C - 10.8 °C (WARNING), followed by gradual refrigeration recovery.
- Avoids unrealistic drift or saturation to room temperature (20-25 °C).
"""

import os
import csv
import random
from datetime import datetime, timedelta

OUTPUT_PATH = os.path.join("data", "processed", "modeling_dataset.csv")

# Threshold Definitions
TEMP_MIN_SAFE = 2.0
TEMP_MAX_SAFE = 8.0
TOTAL_SAMPLES = 1200
SAMPLE_INTERVAL_SECONDS = 60  # 1-minute telemetry intervals


def evaluate_status(temperature: float, humidity: float) -> str:
    """
    Evaluates cold-storage safety condition.
    NORMAL: Safe temperature band 2.0 °C <= Temp <= 8.0 °C
    WARNING: Temperature excursion (> 8.0 °C or < 2.0 °C)
    """
    if TEMP_MIN_SAFE <= temperature <= TEMP_MAX_SAFE:
        return "NORMAL"
    return "WARNING"


def generate_modeling_data(
    num_samples: int = TOTAL_SAMPLES,
    output_path: str = OUTPUT_PATH,
    start_time: datetime = datetime(2026, 9, 30, 0, 0, 0),
    random_seed: int = 42,
) -> str:
    """
    Simulates a continuous, realistic cold-storage temperature time-series.
    """
    random.seed(random_seed)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Initial states
    current_temp = 4.2
    current_humidity = 73.0
    compressor_cooling = False

    # Anomaly tracking
    in_anomaly = False
    anomaly_phase = "idle"  # 'warming', 'cooling', 'idle'
    anomaly_duration = 0
    anomaly_step = 0
    peak_target = 0.0

    steps_since_last_anomaly = 0
    anomaly_cooldown = 120  # minimum steps between excursion events

    records = []
    current_time = start_time

    for i in range(num_samples):
        steps_since_last_anomaly += 1

        # Check if an excursion event should begin
        if (
            not in_anomaly
            and steps_since_last_anomaly > anomaly_cooldown
            and random.random() < 0.04
        ):
            in_anomaly = True
            anomaly_phase = "warming"
            anomaly_duration = random.randint(18, 28)
            anomaly_step = 0
            peak_target = round(random.uniform(8.6, 10.8), 2)
            steps_since_last_anomaly = 0

        if in_anomaly:
            if anomaly_phase == "warming":
                anomaly_step += 1
                # Gradual warming rate
                warming_rate = (peak_target - current_temp) / max(1, (anomaly_duration - anomaly_step + 1))
                current_temp += round(warming_rate + random.uniform(-0.05, 0.12), 2)
                # Humidity slightly decreases during warm air infiltration
                current_humidity += round(random.uniform(-0.4, 0.1), 1)

                if current_temp >= peak_target or anomaly_step >= anomaly_duration:
                    anomaly_phase = "cooling"
                    recovery_steps = random.randint(22, 32)
                    recovery_step = 0

            elif anomaly_phase == "cooling":
                recovery_step += 1
                # High-capacity cooling recovery back to safe zone (~4.0 °C)
                cooling_rate = (current_temp - 4.2) / max(1, (recovery_steps - recovery_step + 1))
                current_temp -= round(cooling_rate + random.uniform(-0.04, 0.08), 2)
                current_humidity += round(random.uniform(-0.1, 0.4), 1)

                if current_temp <= 4.8 or recovery_step >= recovery_steps:
                    in_anomaly = False
                    anomaly_phase = "idle"
                    compressor_cooling = True

        else:
            # Normal thermostatic cycle (between ~3.2 °C and ~5.8 °C)
            if compressor_cooling:
                # Compressor is actively chilling
                current_temp -= round(random.uniform(0.08, 0.18), 2)
                current_humidity += round(random.uniform(-0.2, 0.3), 1)
                if current_temp <= 3.4:
                    compressor_cooling = False  # Setpoint reached; compressor shuts off
            else:
                # Compressor is idle; minor ambient heat ingress
                current_temp += round(random.uniform(0.05, 0.14), 2)
                current_humidity += round(random.uniform(-0.3, 0.2), 1)
                if current_temp >= 5.6:
                    compressor_cooling = True  # High threshold reached; compressor kicks in

            # Add subtle thermal sensor noise
            current_temp += round(random.gauss(0, 0.03), 2)

        # Enforce realistic cold-storage physical bounds
        current_temp = max(2.1, min(11.5, round(current_temp, 2)))
        current_humidity = max(55.0, min(82.0, round(current_humidity, 1)))

        status = evaluate_status(current_temp, current_humidity)
        time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

        records.append({
            "Timestamp": time_str,
            "Temperature": f"{current_temp:.2f}",
            "Humidity": f"{current_humidity:.1f}",
            "Status": status,
        })

        current_time += timedelta(seconds=SAMPLE_INTERVAL_SECONDS)

    # Write to CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Temperature", "Humidity", "Status"])
        for r in records:
            writer.writerow([r["Timestamp"], r["Temperature"], r["Humidity"], r["Status"]])

    print(f"Successfully generated {len(records)} realistic observations at: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_modeling_data()

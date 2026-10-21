"""
IoT-Based Cold-Storage Monitoring - Phase 4: Risk Detection & Early Warning System

Utilizes the trained Phase 3 LSTM model to generate sequential temperature forecasts,
identifies persistent upward trends, and categorizes operational risk into:
  - NORMAL: Safe operating band (2.0°C - 8.0°C) with no persistent rising trend.
  - EARLY WARNING: Temperature within safe band, but exhibits a persistent abnormal rising trend.
  - WARNING: Temperature exceeds 8.0°C or drops below 2.0°C (threshold violation).
"""

import os
import sys
import json
import pickle
import argparse
import numpy as np
import pandas as pd
import matplotlib
# Non-interactive backend for server/script plotting
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Suppress verbose TensorFlow logging
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf
from tensorflow.keras.models import load_model

# Terminal encoding for Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Default Paths
MODEL_PATH = os.path.join("models", "lstm_temperature_model.keras")
SCALER_PATH = os.path.join("data", "processed", "scaler.pkl")
RAW_DATA_PATH = os.path.join("data", "processed", "modeling_dataset.csv")
X_PATH = os.path.join("data", "processed", "X.npy")
Y_PATH = os.path.join("data", "processed", "y.npy")
OUTPUT_CSV_PATH = os.path.join("data", "processed", "risk_predictions.csv")
OUTPUT_PLOT_PATH = os.path.join("models", "risk_detection_plot.png")
OUTPUT_SUMMARY_PATH = os.path.join("models", "risk_summary.json")

# Configurable Thresholds
SAFE_TEMP_MIN = 2.0
SAFE_TEMP_MAX = 8.0
DEFAULT_TREND_WINDOW = 4
DEFAULT_MIN_RISE_DELTA = 0.40  # Cumulative rise in °C over window to trigger rising trend alert


class ColdStorageRiskDetector:
    """
    Evaluates real-time / sequential temperature forecasts against static thresholds
    and dynamic trend trajectories.
    """

    def __init__(
        self,
        safe_min: float = SAFE_TEMP_MIN,
        safe_max: float = SAFE_TEMP_MAX,
        trend_window: int = DEFAULT_TREND_WINDOW,
        min_rise_delta: float = DEFAULT_MIN_RISE_DELTA,
    ):
        self.safe_min = safe_min
        self.safe_max = safe_max
        self.trend_window = trend_window
        self.min_rise_delta = min_rise_delta

    def determine_trend(self, recent_predictions: list[float]) -> tuple[str, bool]:
        """
        Determines the temperature trend over recent predictions.
        Returns (trend_label, is_persistent_rising).
        """
        if len(recent_predictions) < self.trend_window:
            return "STABLE", False

        window = recent_predictions[-self.trend_window :]
        # Check if consecutive steps are strictly increasing
        is_consec_rising = all(window[j] > window[j - 1] for j in range(1, len(window)))
        delta_rise = window[-1] - window[0]

        if is_consec_rising and (delta_rise >= self.min_rise_delta):
            return "RISING", True
        elif all(window[j] < window[j - 1] for j in range(1, len(window))):
            return "FALLING", False
        elif is_consec_rising:
            return "SLIGHT RISE", False
        else:
            return "STABLE", False

    def evaluate_risk(
        self, predicted_temp: float, trend: str, is_rising_alert: bool
    ) -> tuple[str, str]:
        """
        Assigns risk level and explanatory alert message based on predicted value and trend.
        """
        # 1. Critical threshold violation (WARNING)
        if predicted_temp > self.safe_max:
            return "WARNING", f"Temperature exceeded safe upper threshold ({predicted_temp:.2f} °C > {self.safe_max} °C)"
        if predicted_temp < self.safe_min:
            return "WARNING", f"Temperature dropped below safe lower threshold ({predicted_temp:.2f} °C < {self.safe_min} °C)"

        # 2. Early Warning: within safe range, but persistent rising trend detected
        if is_rising_alert:
            return "EARLY WARNING", f"Continuous abnormal temperature increase detected ({trend} trend)"

        # 3. Normal safe operation
        return "NORMAL", "Operating within safe cold-storage range"


def run_risk_pipeline(
    model_path: str = MODEL_PATH,
    scaler_path: str = SCALER_PATH,
    x_path: str = X_PATH,
    y_path: str = Y_PATH,
    raw_data_path: str = RAW_DATA_PATH,
    output_csv: str = OUTPUT_CSV_PATH,
    output_plot: str = OUTPUT_PLOT_PATH,
    output_summary: str = OUTPUT_SUMMARY_PATH,
    safe_min: float = SAFE_TEMP_MIN,
    safe_max: float = SAFE_TEMP_MAX,
    trend_window: int = DEFAULT_TREND_WINDOW,
    min_rise_delta: float = DEFAULT_MIN_RISE_DELTA,
):
    """Executes the Phase 4 Risk Detection Pipeline."""
    print("=" * 65)
    print("Cold-Storage Monitoring - Phase 4: Risk Detection & Early Warning")
    print("=" * 65)

    # 1. Load artifacts
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at: {model_path}. Run train_lstm.py first.")
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(f"Scaler not found at: {scaler_path}.")

    model = load_model(model_path)
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)

    X = np.load(x_path)
    y = np.load(y_path)
    df_raw = pd.read_csv(raw_data_path)

    # In sequence generation, X[i] uses past 10 readings to forecast reading at index i + 10
    window_size = X.shape[1]
    timestamps = df_raw["Timestamp"].iloc[window_size:].reset_index(drop=True)

    print(f"Loaded feature matrix X      : {X.shape}")
    print(f"Generating LSTM forecasts...")

    # 2. Generate predictions and inverse-transform
    y_pred_scaled = model.predict(X, verbose=0)
    y_pred_celsius = scaler.inverse_transform(y_pred_scaled).flatten()
    y_actual_celsius = scaler.inverse_transform(y).flatten()

    detector = ColdStorageRiskDetector(
        safe_min=safe_min,
        safe_max=safe_max,
        trend_window=trend_window,
        min_rise_delta=min_rise_delta,
    )

    # 3. Sequential evaluation
    results = []
    recent_history = []
    normal_count = 0
    early_warning_count = 0
    warning_count = 0
    rising_trend_count = 0

    sample_early_warnings = []
    sample_warnings = []

    for i in range(len(y_pred_celsius)):
        pred_temp = float(y_pred_celsius[i])
        actual_temp = float(y_actual_celsius[i])
        tstamp = str(timestamps[i]) if i < len(timestamps) else f"Step_{i}"

        recent_history.append(pred_temp)
        trend, is_rising_alert = detector.determine_trend(recent_history)
        if trend == "RISING":
            rising_trend_count += 1

        risk_level, alert_msg = detector.evaluate_risk(pred_temp, trend, is_rising_alert)

        if risk_level == "NORMAL":
            normal_count += 1
        elif risk_level == "EARLY WARNING":
            early_warning_count += 1
            if len(sample_early_warnings) < 3:
                sample_early_warnings.append({
                    "Timestamp": tstamp,
                    "Actual_Temperature": round(actual_temp, 2),
                    "Predicted_Temperature": round(pred_temp, 2),
                    "Trend": trend,
                    "Risk_Level": risk_level,
                    "Alert": alert_msg,
                })
        elif risk_level == "WARNING":
            warning_count += 1
            if len(sample_warnings) < 3:
                sample_warnings.append({
                    "Timestamp": tstamp,
                    "Actual_Temperature": round(actual_temp, 2),
                    "Predicted_Temperature": round(pred_temp, 2),
                    "Trend": trend,
                    "Risk_Level": risk_level,
                    "Alert": alert_msg,
                })

        results.append({
            "Timestamp": tstamp,
            "Actual_Temperature": f"{actual_temp:.2f}",
            "Predicted_Temperature": f"{pred_temp:.2f}",
            "Temperature_Trend": trend,
            "Risk_Level": risk_level,
            "Alert_Message": alert_msg,
        })

    # 4. Save results to CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_results = pd.DataFrame(results)
    df_results.to_csv(output_csv, index=False)
    print(f"Risk evaluation results saved to: {output_csv}")

    # 5. Generate Risk Detection Plot
    os.makedirs(os.path.dirname(output_plot), exist_ok=True)
    plt.figure(figsize=(14, 6), dpi=150)

    # Plot actual and predicted lines
    plt.plot(y_actual_celsius, label="Actual Temperature (°C)", color="#1f77b4", linewidth=1.5, alpha=0.85)
    plt.plot(y_pred_celsius, label="Predicted Temperature (°C)", color="#2ca02c", linewidth=1.5, linestyle="--", alpha=0.9)

    # Safety limits
    plt.axhline(y=safe_max, color="#d62728", linestyle=":", linewidth=1.5, label=f"Upper Safety Limit ({safe_max}°C)")
    plt.axhline(y=safe_min, color="#7f7f7f", linestyle=":", linewidth=1.2, label=f"Lower Safety Limit ({safe_min}°C)")

    # Color code points according to risk level
    ew_indices = [idx for idx, r in enumerate(results) if r["Risk_Level"] == "EARLY WARNING"]
    w_indices = [idx for idx, r in enumerate(results) if r["Risk_Level"] == "WARNING"]

    if ew_indices:
        plt.scatter(
            ew_indices,
            y_pred_celsius[ew_indices],
            color="#ff7f0e",
            s=22,
            zorder=5,
            label="EARLY WARNING (Rising Trend)",
        )
    if w_indices:
        plt.scatter(
            w_indices,
            y_pred_celsius[w_indices],
            color="#d62728",
            s=28,
            marker="^",
            zorder=6,
            label="WARNING (Threshold Violation)",
        )

    plt.title("Cold-Storage Temperature Forecast & Proactive Risk Detection", fontsize=13, fontweight="bold")
    plt.xlabel("Sample Timeline Index", fontsize=11)
    plt.ylabel("Temperature (°C)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper left", framealpha=0.9)
    plt.tight_layout()
    plt.savefig(output_plot)
    plt.close()
    print(f"Risk detection visualization saved to: {output_plot}")

    # 6. Save JSON Summary
    summary_data = {
        "total_predictions": len(y_pred_celsius),
        "normal_count": normal_count,
        "early_warning_count": early_warning_count,
        "warning_count": warning_count,
        "rising_trend_detections": rising_trend_count,
        "maximum_predicted_temperature": round(float(y_pred_celsius.max()), 2),
        "minimum_predicted_temperature": round(float(y_pred_celsius.min()), 2),
        "safety_thresholds": {
            "safe_min_celsius": safe_min,
            "safe_max_celsius": safe_max,
            "trend_window_steps": trend_window,
            "min_rise_delta_celsius": min_rise_delta,
        },
        "sample_cases": {
            "early_warning": sample_early_warnings[0] if sample_early_warnings else None,
            "warning": sample_warnings[0] if sample_warnings else None,
        },
        "artifacts_generated": [output_csv, output_plot, output_summary],
    }

    with open(output_summary, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=4)
    print(f"Risk summary saved to: {output_summary}")

    # 7. Print Console Summary
    print("\n" + "=" * 65)
    print("Risk Detection Summary")
    print("=" * 65)
    print(f"Total Predictions Evaluated   : {len(y_pred_celsius)}")
    print(f"NORMAL Readings               : {normal_count} ({normal_count/len(y_pred_celsius)*100:.1f}%)")
    print(f"EARLY WARNING (Rising Trend)  : {early_warning_count} ({early_warning_count/len(y_pred_celsius)*100:.1f}%)")
    print(f"WARNING (Threshold Breach)    : {warning_count} ({warning_count/len(y_pred_celsius)*100:.1f}%)")
    print(f"Rising Trend Sequences        : {rising_trend_count}")
    print(f"Max Predicted Temperature     : {summary_data['maximum_predicted_temperature']} °C")
    print(f"Min Predicted Temperature     : {summary_data['minimum_predicted_temperature']} °C")

    if sample_early_warnings:
        ew = sample_early_warnings[0]
        print("\n--- Sample Early Warning Case ---")
        print(f"Timestamp             : {ew['Timestamp']}")
        print(f"Actual Temperature    : {ew['Actual_Temperature']} °C")
        print(f"Predicted Temperature : {ew['Predicted_Temperature']} °C")
        print(f"Trend                 : {ew['Trend']}")
        print(f"Risk Level            : {ew['Risk_Level']}")
        print(f"Alert                 : {ew['Alert']}")

    if sample_warnings:
        w = sample_warnings[0]
        print("\n--- Sample Warning Case ---")
        print(f"Timestamp             : {w['Timestamp']}")
        print(f"Actual Temperature    : {w['Actual_Temperature']} °C")
        print(f"Predicted Temperature : {w['Predicted_Temperature']} °C")
        print(f"Trend                 : {w['Trend']}")
        print(f"Risk Level            : {w['Risk_Level']}")
        print(f"Alert                 : {w['Alert']}")

    print("=" * 65)
    return summary_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 4: Cold-Storage Risk Detection System")
    parser.add_argument("--safe-min", type=float, default=SAFE_TEMP_MIN, help="Lower safety threshold in °C")
    parser.add_argument("--safe-max", type=float, default=SAFE_TEMP_MAX, help="Upper safety threshold in °C")
    parser.add_argument("--trend-window", type=int, default=DEFAULT_TREND_WINDOW, help="Number of steps for trend analysis")
    parser.add_argument("--min-rise", type=float, default=DEFAULT_MIN_RISE_DELTA, help="Minimum cumulative rise in °C")
    args = parser.parse_args()

    run_risk_pipeline(
        safe_min=args.safe_min,
        safe_max=args.safe_max,
        trend_window=args.trend_window,
        min_rise_delta=args.min_rise,
    )

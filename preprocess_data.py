"""
IoT-Based Cold-Storage Monitoring - Phase 2: Data Preprocessing Pipeline

Prepares clean, normalized time-series sequence datasets for LSTM temperature forecasting.
Extracts past 10 temperature readings to forecast the next temperature reading.
"""

import os
import sys
import json
import pickle
import argparse
import numpy as np
import pandas as pd
import matplotlib
# Use non-interactive backend for server/script plotting
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

# Standard terminal encoding configuration
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Default Paths
MODELING_CSV_PATH = os.path.join("data", "processed", "modeling_dataset.csv")
RAW_CSV_PATH = os.path.join("data", "sensor_data.csv")
DEFAULT_INPUT_CSV = MODELING_CSV_PATH if os.path.exists(MODELING_CSV_PATH) else RAW_CSV_PATH
DEFAULT_OUTPUT_DIR = os.path.join("data", "processed")
DEFAULT_WINDOW_SIZE = 10


def load_and_validate_data(csv_path: str) -> tuple[pd.DataFrame, dict]:
    """
    Loads raw sensor CSV, validates timestamps, sorts chronologically,
    and checks for missing or invalid data.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Input file not found at: {csv_path}")

    df = pd.read_csv(csv_path)

    # Initial statistics before preprocessing
    raw_row_count = len(df)
    missing_before = df.isnull().sum().to_dict()

    # 1. Validate and convert timestamp column
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    invalid_timestamps = df["Timestamp"].isnull().sum()
    if invalid_timestamps > 0:
        print(f"[Warning] Dropping {invalid_timestamps} rows with unparseable timestamps.")
        df = df.dropna(subset=["Timestamp"])

    # 2. Sort records chronologically
    df = df.sort_values(by="Timestamp").reset_index(drop=True)

    # 3. Ensure numerical types for Temperature and Humidity
    df["Temperature"] = pd.to_numeric(df["Temperature"], errors="coerce")
    df["Humidity"] = pd.to_numeric(df["Humidity"], errors="coerce")

    # 4. Handle missing numerical values safely (forward-fill then backward-fill)
    if df["Temperature"].isnull().any() or df["Humidity"].isnull().any():
        df["Temperature"] = df["Temperature"].ffill().bfill()
        df["Humidity"] = df["Humidity"].ffill().bfill()

    # Drop any remaining unfillable rows if present
    df = df.dropna(subset=["Temperature", "Humidity"]).reset_index(drop=True)

    stats = {
        "raw_rows": raw_row_count,
        "clean_rows": len(df),
        "columns": list(df.columns),
        "missing_values_found": missing_before,
        "temperature_min": float(df["Temperature"].min()),
        "temperature_max": float(df["Temperature"].max()),
        "temperature_mean": round(float(df["Temperature"].mean()), 2),
        "humidity_min": float(df["Humidity"].min()),
        "humidity_max": float(df["Humidity"].max()),
        "humidity_mean": round(float(df["Humidity"].mean()), 2),
        "timestamp_start": str(df["Timestamp"].min()),
        "timestamp_end": str(df["Timestamp"].max()),
    }

    return df, stats


def create_sequences(series: np.ndarray, window_size: int = DEFAULT_WINDOW_SIZE) -> tuple[np.ndarray, np.ndarray]:
    """
    Creates sliding-window sequences for LSTM forecasting:
    Past `window_size` readings (Input X) -> Next reading (Target y).
    """
    X, y = [], []
    for i in range(len(series) - window_size):
        X.append(series[i : i + window_size])
        y.append(series[i + window_size])
    return np.array(X), np.array(y)


def generate_timeseries_plot(df: pd.DataFrame, output_path: str):
    """
    Generates a clean temperature time-series plot for visual dataset inspection.
    """
    plt.figure(figsize=(12, 5), dpi=150)
    plt.plot(df["Timestamp"], df["Temperature"], color="#1f77b4", linewidth=1.5, label="Temperature (°C)")

    # Highlight cold-storage threshold boundaries
    plt.axhline(y=8.0, color="#d62728", linestyle="--", alpha=0.7, label="Upper Warning Limit (8.0°C)")
    plt.axhline(y=2.0, color="#2ca02c", linestyle="--", alpha=0.7, label="Lower Warning Limit (2.0°C)")

    plt.title("Cold Storage Temperature Telemetry - Time Series", fontsize=13, fontweight="bold")
    plt.xlabel("Timestamp", fontsize=11)
    plt.ylabel("Temperature (°C)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper left")
    plt.xticks(rotation=25)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def run_pipeline(
    input_csv: str = DEFAULT_INPUT_CSV,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    window_size: int = DEFAULT_WINDOW_SIZE,
):
    """Executes the complete Phase 2 preprocessing and dataset generation pipeline."""
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("Cold-Storage Monitoring - Phase 2: Data Preprocessing")
    print("=" * 60)
    print(f"Loading raw telemetry from : {input_csv}")
    print(f"Destination directory      : {output_dir}")
    print(f"Sequence window size       : {window_size} timesteps")

    # Step 1: Load, validate, and clean
    df, stats = load_and_validate_data(input_csv)

    if len(df) <= window_size:
        raise ValueError(
            f"Dataset has only {len(df)} records, which is not enough for window_size={window_size}."
            " Please run the simulator longer to collect more data."
        )

    # Step 2: Save cleaned dataset preserving humidity and status features
    cleaned_csv_path = os.path.join(output_dir, "cleaned_sensor_data.csv")
    df.to_csv(cleaned_csv_path, index=False)

    # Step 3: Extract temperature & normalize using MinMaxScaler(0, 1)
    raw_temps = df["Temperature"].values.reshape(-1, 1)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_temps = scaler.fit_transform(raw_temps)

    # Save fitted scaler for Phase 3 model evaluation and inference
    scaler_path = os.path.join(output_dir, "scaler.pkl")
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    # Step 4: Create sequences
    # Scaled sequences for LSTM training: X shape (N, window_size, 1), y shape (N, 1)
    X_scaled, y_scaled = create_sequences(scaled_temps, window_size=window_size)
    # Raw sequences for human verification: X_raw shape (N, window_size), y_raw shape (N,)
    X_raw, y_raw = create_sequences(raw_temps.flatten(), window_size=window_size)

    # Save arrays in .npy format
    x_scaled_path = os.path.join(output_dir, "X.npy")
    y_scaled_path = os.path.join(output_dir, "y.npy")
    x_raw_path = os.path.join(output_dir, "X_raw.npy")
    y_raw_path = os.path.join(output_dir, "y_raw.npy")

    np.save(x_scaled_path, X_scaled)
    np.save(y_scaled_path, y_scaled)
    np.save(x_raw_path, X_raw)
    np.save(y_raw_path, y_raw)

    # Step 5: Generate temperature time-series plot
    plot_path = os.path.join(output_dir, "temperature_timeseries.png")
    generate_timeseries_plot(df, plot_path)

    # Step 6: Save pipeline metadata
    metadata = {
        "dataset_statistics": stats,
        "preprocessing_config": {
            "window_size": window_size,
            "scaler": "MinMaxScaler(0, 1)",
            "scaler_data_min": float(scaler.data_min_[0]),
            "scaler_data_max": float(scaler.data_max_[0]),
            "scaler_scale": float(scaler.scale_[0]),
        },
        "sequence_shapes": {
            "X_shape": list(X_scaled.shape),
            "y_shape": list(y_scaled.shape),
            "X_raw_shape": list(X_raw.shape),
            "y_raw_shape": list(y_raw.shape),
        },
        "files_generated": [
            "cleaned_sensor_data.csv",
            "X.npy",
            "y.npy",
            "X_raw.npy",
            "y_raw.npy",
            "scaler.pkl",
            "temperature_timeseries.png",
            "metadata.json",
        ],
    }

    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    # Step 7: Print detailed summary report
    print("\n--- 1. Dataset Statistics ---")
    print(f"Total Rows Loaded        : {stats['raw_rows']}")
    print(f"Total Clean Records      : {stats['clean_rows']}")
    print(f"Columns                  : {stats['columns']}")
    print(f"Data Types               : Timestamp (datetime64[ns]), Temperature (float64), Humidity (float64), Status (object)")
    print(f"Missing Values Checked   : {stats['missing_values_found']} (All resolved: 0)")
    print(f"Temperature Range        : {stats['temperature_min']} °C to {stats['temperature_max']} °C (Mean: {stats['temperature_mean']} °C)")
    print(f"Humidity Range           : {stats['humidity_min']} % to {stats['humidity_max']} % (Mean: {stats['humidity_mean']} %)")
    print(f"Timestamp Range          : {stats['timestamp_start']}  -->  {stats['timestamp_end']}")

    print("\n--- 2. LSTM Sequence Construction ---")
    print(f"Input Sequence Shape (X) : {X_scaled.shape}  [samples, timesteps, features]")
    print(f"Target Output Shape (y)  : {y_scaled.shape}  [samples, features]")

    print("\n--- 3. Sample Sequence Pair (Index 0) ---")
    print(f"Raw Input (Past 10 °C)   : {list(np.round(X_raw[0], 2))}")
    print(f"Raw Target (Next 1 °C)   : {round(float(y_raw[0]), 2)}")
    print(f"Scaled Input (Normalized): {list(np.round(X_scaled[0].flatten(), 4))}")
    print(f"Scaled Target (Norm)     : {round(float(y_scaled[0][0]), 4)}")

    print("\n--- 4. Generated Artifacts in data/processed/ ---")
    for fname in metadata["files_generated"]:
        print(f"  ✓ {os.path.join(output_dir, fname)}")

    print("\nPreprocessing pipeline completed successfully.")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cold-Storage Data Preprocessing for LSTM (Phase 2)")
    parser.add_argument("--input", type=str, default=DEFAULT_INPUT_CSV, help="Path to raw sensor_data.csv")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Directory for processed data")
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE, help="Sliding window size (past readings)")
    args = parser.parse_args()

    run_pipeline(input_csv=args.input, output_dir=args.output_dir, window_size=args.window_size)

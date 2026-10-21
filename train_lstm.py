"""
IoT-Based Cold-Storage Monitoring - Phase 3: LSTM Model Training

Builds, trains, and evaluates a 2-layer LSTM neural network for one-step-ahead
temperature forecasting in cold-storage environments.
"""

import os
import sys
import json
import pickle
import argparse
import numpy as np
import matplotlib
# Use non-interactive backend for script plotting
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Silence excessive TensorFlow log noise
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, LSTM, Dense
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Configure UTF-8 encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Paths
PROCESSED_DATA_DIR = os.path.join("data", "processed")
MODELS_DIR = "models"
MODEL_SAVE_PATH = os.path.join(MODELS_DIR, "lstm_temperature_model.keras")
METRICS_SAVE_PATH = os.path.join(MODELS_DIR, "training_metrics.json")
LOSS_PLOT_PATH = os.path.join(MODELS_DIR, "training_validation_loss.png")
PREDICTION_PLOT_PATH = os.path.join(MODELS_DIR, "test_actual_vs_predicted.png")


def load_data(data_dir: str = PROCESSED_DATA_DIR):
    """Loads preprocessed LSTM sequences and the fitted scaler."""
    x_path = os.path.join(data_dir, "X.npy")
    y_path = os.path.join(data_dir, "y.npy")
    scaler_path = os.path.join(data_dir, "scaler.pkl")

    if not os.path.exists(x_path) or not os.path.exists(y_path):
        raise FileNotFoundError(
            f"Preprocessed arrays not found in {data_dir}. Run preprocess_data.py first."
        )

    X = np.load(x_path)
    y = np.load(y_path)

    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)

    return X, y, scaler


def split_chronological_data(X: np.ndarray, y: np.ndarray, train_ratio: float = 0.8, val_ratio: float = 0.15):
    """
    Splits time-series data chronologically (NO random shuffling).
    - train_ratio: portion allocated to training + validation (e.g. 0.80)
    - val_ratio: portion of the training set used for validation
    """
    total_samples = len(X)
    train_val_end = int(total_samples * train_ratio)

    val_count = int(train_val_end * val_ratio)
    train_end = train_val_end - val_count

    X_train, y_train = X[:train_end], y[:train_end]
    X_val, y_val = X[train_end:train_val_end], y[train_end:train_val_end]
    X_test, y_test = X[train_val_end:], y[train_val_end:]

    return (X_train, y_train), (X_val, y_val), (X_test, y_test)


def build_lstm_model(input_shape=(10, 1)) -> Sequential:
    """
    Constructs beginner-friendly 2-layer LSTM architecture:
    Input: (10, 1) -> LSTM(64) -> LSTM(32) -> Dense(1) -> Output
    """
    model = Sequential([
        Input(shape=input_shape),
        LSTM(64, return_sequences=True, activation="tanh", name="lstm_layer_1"),
        LSTM(32, return_sequences=False, activation="tanh", name="lstm_layer_2"),
        Dense(1, activation="linear", name="dense_output")
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="mse",
        metrics=["mae"]
    )
    return model


def plot_loss_curves(history, output_path: str):
    """Plots training and validation loss curves over epochs."""
    plt.figure(figsize=(9, 4.5), dpi=150)
    epochs_range = range(1, len(history.history["loss"]) + 1)
    plt.plot(epochs_range, history.history["loss"], label="Training Loss (MSE)", color="#1f77b4", linewidth=1.8)
    plt.plot(epochs_range, history.history["val_loss"], label="Validation Loss (MSE)", color="#ff7f0e", linestyle="--", linewidth=1.8)

    plt.title("LSTM Temperature Forecasting - Training & Validation Loss", fontsize=12, fontweight="bold")
    plt.xlabel("Epoch", fontsize=10)
    plt.ylabel("Loss (MSE)", fontsize=10)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_actual_vs_predicted(actual: np.ndarray, predicted: np.ndarray, output_path: str):
    """Plots actual vs predicted temperatures on the test set."""
    plt.figure(figsize=(12, 5), dpi=150)
    plt.plot(actual, label="Actual Temperature (°C)", color="#1f77b4", linewidth=1.8)
    plt.plot(predicted, label="Predicted Temperature (°C)", color="#d62728", linestyle="--", linewidth=1.6)

    # Reference cold-storage limits
    plt.axhline(y=8.0, color="#7f7f7f", linestyle=":", alpha=0.7, label="Safe Threshold (8.0°C)")

    plt.title("Test Set Evaluation - Actual vs LSTM Predicted Temperature", fontsize=12, fontweight="bold")
    plt.xlabel("Test Sample Index (Chronological)", fontsize=10)
    plt.ylabel("Temperature (°C)", fontsize=10)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def train_and_evaluate(epochs: int = 60, batch_size: int = 32):
    """Executes the full Phase 3 LSTM training and evaluation pipeline."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("=" * 65)
    print("Cold-Storage Monitoring - Phase 3: LSTM Model Training")
    print("=" * 65)

    # 1. Load data
    X, y, scaler = load_data(PROCESSED_DATA_DIR)
    print(f"Loaded feature matrix X  : {X.shape}")
    print(f"Loaded target vector y   : {y.shape}")

    # 2. Chronological split
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = split_chronological_data(X, y)
    print(f"\nChronological Data Splitting:")
    print(f"  - Training samples     : {len(X_train)} ({len(X_train)/len(X)*100:.1f}%)")
    print(f"  - Validation samples   : {len(X_val)} ({len(X_val)/len(X)*100:.1f}%)")
    print(f"  - Testing samples      : {len(X_test)} ({len(X_test)/len(X)*100:.1f}%)")

    # 3. Build model
    model = build_lstm_model(input_shape=(X.shape[1], X.shape[2]))
    print("\nModel Architecture:")
    model.summary(print_fn=lambda x: print(f"  {x}"))

    # 4. Train with EarlyStopping
    early_stop = EarlyStopping(
        monitor="val_loss",
        patience=10,
        restore_best_weights=True,
        verbose=1
    )

    print(f"\nBeginning training (max {epochs} epochs, batch size {batch_size})...")
    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stop],
        verbose=1,
        shuffle=False  # Preserve sequential time-series ordering
    )

    completed_epochs = len(history.history["loss"])
    final_train_loss = float(history.history["loss"][-1])
    final_val_loss = float(history.history["val_loss"][-1])

    # 5. Evaluate on Test Set
    y_pred_scaled = model.predict(X_test, verbose=0)

    # Inverse-transform to actual °C
    y_test_actual = scaler.inverse_transform(y_test)
    y_pred_actual = scaler.inverse_transform(y_pred_scaled)

    # Calculate regression metrics in °C
    test_mae = float(mean_absolute_error(y_test_actual, y_pred_actual))
    test_rmse = float(np.sqrt(mean_squared_error(y_test_actual, y_pred_actual)))

    # 6. Generate graphs
    plot_loss_curves(history, LOSS_PLOT_PATH)
    plot_actual_vs_predicted(y_test_actual, y_pred_actual, PREDICTION_PLOT_PATH)

    # 7. Save model and metrics
    model.save(MODEL_SAVE_PATH)

    metrics_data = {
        "model_architecture": {
            "input_shape": [X.shape[1], X.shape[2]],
            "layers": [
                {"type": "LSTM", "units": 64, "return_sequences": True},
                {"type": "LSTM", "units": 32, "return_sequences": False},
                {"type": "Dense", "units": 1, "activation": "linear"}
            ],
            "optimizer": "Adam (lr=0.001)",
            "loss_function": "MSE"
        },
        "dataset_split": {
            "total_samples": len(X),
            "training_samples": len(X_train),
            "validation_samples": len(X_val),
            "testing_samples": len(X_test)
        },
        "training_performance": {
            "epochs_completed": completed_epochs,
            "final_training_loss_mse": round(final_train_loss, 6),
            "final_validation_loss_mse": round(final_val_loss, 6),
            "test_mae_celsius": round(test_mae, 4),
            "test_rmse_celsius": round(test_rmse, 4)
        },
        "artifacts_generated": [
            MODEL_SAVE_PATH,
            LOSS_PLOT_PATH,
            PREDICTION_PLOT_PATH,
            METRICS_SAVE_PATH
        ]
    }

    with open(METRICS_SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=4)

    # 8. Display Training and Evaluation Summary
    print("\n" + "=" * 65)
    print("Training Summary & Evaluation Results")
    print("=" * 65)
    print(f"Epochs Completed         : {completed_epochs}")
    print(f"Final Training Loss (MSE): {final_train_loss:.6f}")
    print(f"Final Val Loss (MSE)     : {final_val_loss:.6f}")
    print(f"Test MAE                 : {test_mae:.4f} °C")
    print(f"Test RMSE                : {test_rmse:.4f} °C")

    # Display 10 sample predictions
    print("\n--- Sample Test Predictions (First 10) ---")
    for i in range(min(10, len(y_test_actual))):
        actual_val = float(y_test_actual[i][0])
        pred_val = float(y_pred_actual[i][0])
        print(f"Actual Temperature : {actual_val:5.2f} °C  |  Predicted Temperature: {pred_val:5.2f} °C  (Diff: {abs(actual_val - pred_val):4.2f} °C)")

    print("\n--- Saved Artifacts ---")
    print(f"  ✓ Trained Model         : {MODEL_SAVE_PATH}")
    print(f"  ✓ Loss Curve Plot       : {LOSS_PLOT_PATH}")
    print(f"  ✓ Prediction Plot       : {PREDICTION_PLOT_PATH}")
    print(f"  ✓ Metrics Summary       : {METRICS_SAVE_PATH}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train LSTM Temperature Forecasting Model (Phase 3)")
    parser.add_argument("--epochs", type=int, default=60, help="Maximum training epochs (default: 60)")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size (default: 32)")
    args = parser.parse_args()

    train_and_evaluate(epochs=args.epochs, batch_size=args.batch_size)

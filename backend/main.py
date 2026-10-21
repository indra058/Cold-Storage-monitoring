"""
FastAPI Backend & WebSocket Stream for Cold-Storage Monitoring (Phase 6.1)

Architecture:
  ESP32 Simulator (or Hardware) -> POST /api/sensor -> LSTM Model -> Risk Detection -> WebSocket (/ws/live) -> React Dashboard
"""

import os
import sys
import csv
import time
import pickle
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
import numpy as np

# Suppress verbose TensorFlow logging
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf
from tensorflow.keras.models import load_model
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Relative import of the sensor simulator (used as fallback when no external simulator is posting)
from backend.simulator import LiveSensorSimulator

# Path resolution to project root
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "lstm_temperature_model.keras"
SCALER_PATH = BASE_DIR / "data" / "processed" / "scaler.pkl"
LIVE_CSV_PATH = BASE_DIR / "data" / "live_sensor_data.csv"

# Configurable Risk Detection Constants
SAFE_TEMP_MIN = 2.0
SAFE_TEMP_MAX = 8.0
TREND_WINDOW = 4
MIN_RISE_DELTA = 0.40  # Cumulative rise in °C over TREND_WINDOW to trigger RISING trend


class SensorReading(BaseModel):
    """Telemetry payload format matching ESP32 / DHT22 transmissions."""
    device_id: str = Field(default="ESP32_01", description="Device Identifier")
    timestamp: str = Field(description="Timestamp formatted as YYYY-MM-DD HH:MM:SS")
    temperature: float = Field(description="Ambient temperature in °C")
    humidity: float = Field(description="Relative humidity in %")


class RiskEvaluator:
    """Evaluates temperature trends and risk levels for real-time monitoring."""

    def __init__(
        self,
        safe_min: float = SAFE_TEMP_MIN,
        safe_max: float = SAFE_TEMP_MAX,
        trend_window: int = TREND_WINDOW,
        min_rise_delta: float = MIN_RISE_DELTA,
    ):
        self.safe_min = safe_min
        self.safe_max = safe_max
        self.trend_window = trend_window
        self.min_rise_delta = min_rise_delta

    def evaluate(self, predicted_temp: float, recent_predictions: list[float], current_temp: float = None) -> tuple[str, str, str]:
        """
        Calculates trend, risk_level, and alert message.
        Returns: (trend, risk_level, alert_message)
        """
        trend = "STABLE"
        is_rising_trend = False

        if len(recent_predictions) >= self.trend_window:
            window = recent_predictions[-self.trend_window:]
            # Check strictly increasing streak
            is_consec_rising = all(window[j] > window[j - 1] for j in range(1, len(window)))
            delta_rise = window[-1] - window[0]

            if is_consec_rising and delta_rise >= self.min_rise_delta:
                trend = "RISING"
                is_rising_trend = True
            elif all(window[j] < window[j - 1] for j in range(1, len(window))):
                trend = "FALLING"
            elif is_consec_rising:
                trend = "SLIGHT RISE"
            else:
                trend = "STABLE"

        # Determine Risk Level
        if current_temp is not None and current_temp > self.safe_max:
            risk_level = "WARNING"
            alert = f"Temperature exceeded safe upper threshold ({current_temp:.2f} °C > {self.safe_max} °C)"
        elif predicted_temp > self.safe_max:
            risk_level = "WARNING"
            alert = f"Predicted temperature exceeds safe upper threshold ({predicted_temp:.2f} °C > {self.safe_max} °C)"
        elif (current_temp is not None and current_temp < self.safe_min) or predicted_temp < self.safe_min:
            risk_level = "WARNING"
            alert = f"Temperature dropped below safe lower threshold (< {self.safe_min} °C)"
        elif is_rising_trend:
            risk_level = "EARLY WARNING"
            alert = "Continuous abnormal temperature increase detected"
        else:
            risk_level = "NORMAL"
            alert = "Operating within safe cold-storage range"

        return trend, risk_level, alert


# Global state holders for model, scaler, and active connections
model = None
scaler = None
evaluator = RiskEvaluator()

# Rolling buffers per device ID (preserves 10 previous readings for LSTM input)
device_buffers: dict[str, list[float]] = {}
device_predictions: dict[str, list[float]] = {}
device_latest: dict[str, dict] = {}
recent_alerts: list[dict] = []

# Active WebSocket subscribers
active_websockets: set[WebSocket] = set()

# Timestamp of last received POST /api/sensor
last_post_timestamp: float = 0.0


def load_initial_state_from_csv():
    """Pre-populates device_latest and recent_alerts from existing CSV data on startup."""
    if not LIVE_CSV_PATH.exists():
        return

    try:
        with open(LIVE_CSV_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Pre-populate device_latest with the newest row for each device
        for r in rows:
            dev_id = r.get("Device_ID", "ESP32_01").strip()
            try:
                temp_val = round(float(r["Temperature"]), 2)
                hum_val = round(float(r["Humidity"]), 1)
                pred_val = round(float(r["Predicted_Temperature"]), 2)
            except (ValueError, KeyError):
                continue

            payload = {
                "device_id": dev_id,
                "timestamp": r.get("Timestamp", ""),
                "temperature": temp_val,
                "humidity": hum_val,
                "predicted_temperature": pred_val,
                "trend": r.get("Trend", "STABLE"),
                "risk_level": r.get("Risk_Level", "NORMAL"),
                "alert": r.get("Alert", ""),
            }
            device_latest[dev_id] = payload

            # Collect recent alerts
            if payload["risk_level"] in ("EARLY WARNING", "WARNING"):
                recent_alerts.insert(0, {
                    "device_id": dev_id,
                    "timestamp": payload["timestamp"],
                    "temperature": temp_val,
                    "predicted_temperature": pred_val,
                    "risk_level": payload["risk_level"],
                    "alert": payload["alert"],
                })

        # Cap initial recent alerts to 50
        if len(recent_alerts) > 50:
            del recent_alerts[50:]

        print(f"[Backend Startup] Loaded initial state for devices: {list(device_latest.keys())}")
    except Exception as e:
        print(f"[Backend Startup Warning] Could not pre-populate from CSV: {e}")


def log_to_live_csv(record: dict):
    """Appends live telemetry & risk predictions to data/live_sensor_data.csv."""
    try:
        LIVE_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_exists = LIVE_CSV_PATH.exists()
        with open(LIVE_CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Timestamp",
                    "Temperature",
                    "Humidity",
                    "Predicted_Temperature",
                    "Trend",
                    "Risk_Level",
                    "Alert",
                    "Device_ID"
                ])
            writer.writerow([
                record.get("timestamp"),
                record.get("temperature"),
                record.get("humidity"),
                record.get("predicted_temperature"),
                record.get("trend"),
                record.get("risk_level"),
                record.get("alert"),
                record.get("device_id", "ESP32_01")
            ])
    except Exception as e:
        print(f"[CSV Logging Error] {e}")


async def broadcast_to_websockets(payload: dict):
    """Broadcasts live payload to all connected WebSockets."""
    for ws in list(active_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            active_websockets.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: loads LSTM model and scaler on backend startup."""
    global model, scaler
    print(f"[Backend Startup] Loading LSTM model from: {MODEL_PATH}")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")
    if not SCALER_PATH.exists():
        raise FileNotFoundError(f"Scaler file not found at {SCALER_PATH}")

    model = load_model(str(MODEL_PATH))
    with open(str(SCALER_PATH), "rb") as f:
        scaler = pickle.load(f)

    # Initialize default isolated buffers for standard devices
    for dev in ("ESP32_01", "ESP32_02", "ESP32_03"):
        device_buffers[dev] = [4.15, 4.18, 4.20, 4.22, 4.21, 4.23, 4.25, 4.24, 4.23]
        device_predictions[dev] = []

    # Pre-populate device_latest and recent_alerts from CSV if present
    load_initial_state_from_csv()

    print("[Backend Startup] LSTM model, scaler, and multi-device buffers initialized successfully.")
    yield
    print("[Backend Shutdown] Releasing resources.")


app = FastAPI(
    title="IoT Cold-Storage Monitoring API",
    description="Real-Time Multi-Device LSTM Temperature Forecasting & ESP32 Ingestion Backend (Phase 6.2)",
    version="1.2.0",
    lifespan=lifespan,
)

# CORS configuration allowing local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health status endpoint."""
    return {
        "status": "ok",
        "service": "cold-storage-monitoring",
        "devices_tracked": list(device_latest.keys()),
        "connected_websockets": len(active_websockets)
    }


@app.get("/api/devices")
async def get_all_devices():
    """
    Returns the currently known devices and their latest status.
    If no telemetry has been received, returns an empty list.
    """
    return list(device_latest.values())


@app.get("/api/devices/{device_id}/history")
async def get_device_history(device_id: str, limit: int = 100):
    """
    Returns historical records for the specified device from live_sensor_data.csv.
    Sorted in chronological order up to the requested limit.
    """
    if not LIVE_CSV_PATH.exists():
        return []

    records = []
    try:
        with open(LIVE_CSV_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Device_ID", "").strip() == device_id.strip():
                    try:
                        temp = round(float(row["Temperature"]), 2)
                        hum = round(float(row["Humidity"]), 1)
                        pred = round(float(row["Predicted_Temperature"]), 2)
                    except (ValueError, KeyError):
                        continue

                    records.append({
                        "device_id": row.get("Device_ID", device_id),
                        "timestamp": row.get("Timestamp", ""),
                        "temperature": temp,
                        "humidity": hum,
                        "predicted_temperature": pred,
                        "trend": row.get("Trend", "STABLE"),
                        "risk_level": row.get("Risk_Level", "NORMAL"),
                        "alert": row.get("Alert", ""),
                    })

        # Return the last `limit` records
        if limit and limit > 0 and len(records) > limit:
            records = records[-limit:]

        return records
    except Exception as e:
        print(f"[History API Error] {e}")
        return []


@app.get("/api/alerts")
async def get_active_alerts(limit: int = 20):
    """
    Returns recent records across all devices where risk_level is EARLY WARNING or WARNING.
    Ordered newest first.
    """
    return recent_alerts[:limit]


@app.post("/api/sensor")
async def ingest_sensor_telemetry(reading: SensorReading):
    """
    Receives telemetry from ESP32 (or software ESP32 simulator),
    runs LSTM 1-step ahead forecast, assesses risk, logs to live CSV,
    broadcasts to live WebSocket clients, and returns JSON.
    """
    global last_post_timestamp
    last_post_timestamp = time.time()

    device_id = reading.device_id.strip()
    temp = round(float(reading.temperature), 2)
    hum = round(float(reading.humidity), 1)
    tstamp = reading.timestamp

    # Maintain 10-temperature rolling buffer per device
    if device_id not in device_buffers:
        # Seed initial buffer with nominal readings so sequence has 10 timesteps immediately
        device_buffers[device_id] = [4.15, 4.18, 4.20, 4.22, 4.21, 4.23, 4.25, 4.24, 4.23]
        device_predictions[device_id] = []

    buf = device_buffers[device_id]
    buf.append(temp)
    if len(buf) > 50:
        device_buffers[device_id] = buf[-20:]

    # Safely extract last 10 readings for LSTM input
    if len(buf) < 10:
        padded = [buf[0]] * (10 - len(buf)) + buf
    else:
        padded = buf[-10:]

    seq_inputs = np.array(padded).reshape(-1, 1)
    seq_scaled = scaler.transform(seq_inputs).reshape(1, 10, 1)

    # Execute LSTM prediction
    pred_scaled = model.predict(seq_scaled, verbose=0)
    pred_temp = float(scaler.inverse_transform(pred_scaled)[0, 0])
    pred_temp_rounded = round(pred_temp, 2)

    # Maintain recent prediction history for trend evaluation
    pred_history = device_predictions[device_id]
    pred_history.append(pred_temp_rounded)
    if len(pred_history) > 30:
        device_predictions[device_id] = pred_history[-20:]

    trend, risk_level, alert_msg = evaluator.evaluate(
        pred_temp_rounded, device_predictions[device_id], current_temp=temp
    )

    response_payload = {
        "device_id": device_id,
        "timestamp": tstamp,
        "temperature": temp,
        "humidity": hum,
        "predicted_temperature": pred_temp_rounded,
        "trend": trend,
        "risk_level": risk_level,
        "alert": alert_msg,
    }

    # Update latest status cache for this device
    device_latest[device_id] = response_payload

    # Record to active alerts if risk is abnormal
    if risk_level in ("EARLY WARNING", "WARNING"):
        alert_entry = {
            "device_id": device_id,
            "timestamp": tstamp,
            "temperature": temp,
            "predicted_temperature": pred_temp_rounded,
            "risk_level": risk_level,
            "alert": alert_msg,
        }
        recent_alerts.insert(0, alert_entry)
        if len(recent_alerts) > 50:
            del recent_alerts[50:]

    # Log to live CSV
    log_to_live_csv(response_payload)

    # Broadcast to all connected WebSockets
    await broadcast_to_websockets(response_payload)

    return response_payload


@app.websocket("/ws/live")
async def websocket_live_telemetry(websocket: WebSocket):
    """
    WebSocket endpoint streaming real-time IoT sensor telemetry,
    LSTM 1-step ahead temperature predictions, and trend risk evaluations.
    Supports both direct ESP32 POST streams and autonomous simulation fallback.
    """
    await websocket.accept()
    active_websockets.add(websocket)
    print(f"[WebSocket] Client connected to /ws/live (Active clients: {len(active_websockets)})")

    fallback_simulator = LiveSensorSimulator()
    fallback_history = [4.15, 4.18, 4.20, 4.22, 4.21, 4.23, 4.25, 4.24, 4.23, 4.22]
    fallback_predictions = []

    try:
        while True:
            # Check if external simulator / ESP32 is actively POSTing to /api/sensor
            now = time.time()
            if now - last_post_timestamp < 3.5:
                # External POST stream is active; wait for incoming broadcasts
                await asyncio.sleep(0.5)
                continue

            # Fallback autonomous generation if no external simulator is posting
            reading = fallback_simulator.generate_reading()
            current_temp = reading["temperature"]
            humidity = reading["humidity"]
            timestamp_str = reading["timestamp"]

            fallback_history.append(current_temp)
            seq_inputs = np.array(fallback_history[-10:]).reshape(-1, 1)

            seq_scaled = scaler.transform(seq_inputs).reshape(1, 10, 1)
            pred_scaled = model.predict(seq_scaled, verbose=0)
            pred_temp = float(scaler.inverse_transform(pred_scaled)[0, 0])
            pred_temp_rounded = round(pred_temp, 2)

            fallback_predictions.append(pred_temp_rounded)
            trend, risk_level, alert_msg = evaluator.evaluate(
                pred_temp_rounded, fallback_predictions, current_temp=current_temp
            )

            payload = {
                "device_id": "ESP32_01",
                "timestamp": timestamp_str,
                "temperature": current_temp,
                "humidity": humidity,
                "predicted_temperature": pred_temp_rounded,
                "trend": trend,
                "risk_level": risk_level,
                "alert": alert_msg,
            }

            # Log fallback to CSV as well
            log_to_live_csv(payload)

            await websocket.send_json(payload)
            await asyncio.sleep(1.2)

    except WebSocketDisconnect:
        active_websockets.discard(websocket)
        print(f"[WebSocket] Client disconnected from /ws/live (Active clients: {len(active_websockets)})")
    except Exception as e:
        active_websockets.discard(websocket)
        print(f"[WebSocket Error] {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)

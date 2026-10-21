# IoT-Based Cold-Storage Monitoring using LSTM

This repository implements an end-to-end IoT and Deep Learning pipeline for monitoring cold-storage environments and forecasting temperature excursions using LSTM networks.

---

## Project Structure

```text
IOT and DNN/
├── data/
│   ├── sensor_data.csv             # Phase 1: Raw simulated IoT telemetry
│   └── processed/                  # Phase 2: Cleaned & sequence datasets
│       ├── cleaned_sensor_data.csv # Validated, sorted dataset
│       ├── X.npy                   # Scaled LSTM input sequences (N, 10, 1)
│       ├── y.npy                   # Scaled LSTM targets (N, 1)
│       ├── X_raw.npy               # Raw temperature sequences (°C)
│       ├── y_raw.npy               # Raw temperature targets (°C)
│       ├── scaler.pkl              # Fitted MinMaxScaler object
│       ├── temperature_timeseries.png # Telemetry time-series plot
│       └── metadata.json           # Preprocessing statistics and shapes
├── sensor_simulator.py             # Phase 1: Sensor telemetry simulator
├── preprocess_data.py              # Phase 2: Data cleaning & sequence generation
├── requirements.txt                # Python dependencies
└── README.md                       # Project documentation
```

---

## Requirements & Setup

Install required Python packages:

```bash
pip install -r requirements.txt
```

---

## Phase 1: IoT Sensor Simulation

Simulates cold-storage temperature and humidity telemetry without physical ESP32 hardware.

### 1. Run Continuously (Default)
```bash
python sensor_simulator.py
```
*(Press `Ctrl + C` to stop)*

### 2. Run for a Fixed Number of Samples
```bash
python sensor_simulator.py --samples 20 --interval 0.5
```

---

## Phase 2: Data Preprocessing & LSTM Sequence Generation

Cleans raw telemetry, normalizes temperatures, and structures sliding-window sequences for LSTM forecasting (Past 10 timesteps $\to$ Predict next 1 timestep).

### How to Run Preprocessing
```bash
# Preprocesses the modeling dataset by default
python preprocess_data.py
```

Optional CLI parameters:
```bash
python preprocess_data.py --input data/processed/modeling_dataset.csv --output-dir data/processed --window-size 10
```

---

## Phase 2.5: Modeling Dataset Generation & Realistic Distribution Correction

Generates 1,200 continuous, realistic cold-storage observations with natural compressor cycling (3.2 °C – 5.8 °C) and periodic excursion anomalies (up to 10.8 °C), completely eliminating artificial saturation to room temperature.

### How to Regenerate Modeling Dataset
```bash
python generate_modeling_data.py
```

### Preprocessing Outputs (`data/processed/`)
* **`modeling_dataset.csv`**: 1,200 clean cold-storage observations.
* **`cleaned_sensor_data.csv`**: Chronologically sorted, validated telemetry.
* **`X.npy` & `y.npy`**: Normalized numpy arrays formatted for LSTM `(1190, 10, 1)` and `(1190, 1)`.
* **`X_raw.npy` & `y_raw.npy`**: Unscaled temperature values in °C for verification and baseline comparisons.
* **`scaler.pkl`**: Saved `MinMaxScaler` used to normalize inputs and inverse-transform future predictions.
* **`temperature_timeseries.png`**: Time-series visualization plot.
* **`metadata.json`**: Preprocessing audit trail and dataset metrics.

---

## Phase 3: LSTM Model Training & Evaluation

Builds and trains a 2-layer LSTM deep learning regression model (`Input(10, 1) -> LSTM(64) -> LSTM(32) -> Dense(1)`) to forecast one-step-ahead temperatures. Evaluates predictions in real °C using MAE and RMSE.

### How to Train the Model
```bash
python train_lstm.py
```

Optional CLI parameters:
```bash
python train_lstm.py --epochs 60 --batch-size 32
```

### Phase 3 Outputs (`models/`)
* **`lstm_temperature_model.keras`**: Trained deep learning model file.
* **`training_validation_loss.png`**: Training vs validation loss curve showing convergence.
* **`test_actual_vs_predicted.png`**: Chronological test set evaluation plot comparing actual vs predicted temperature.
* **`training_metrics.json`**: Performance log with final losses, MAE, and RMSE.

---

## Phase 4: Risk Detection & Proactive Early Warning System

Uses the trained Phase 3 LSTM model to evaluate temperature forecasts in real time, detecting persistent rising trends before thresholds are breached, and triggering early warning alerts.

### Safety & Trend Thresholds
* **NORMAL**: $2.0^\circ\text{C} \le \text{Temperature} \le 8.0^\circ\text{C}$ and no persistent rising trend.
* **EARLY WARNING**: Temperature within safe limits ($2.0^\circ\text{C} - 8.0^\circ\text{C}$), but displays continuous abnormal upward trajectory.
* **WARNING**: Predicted temperature breaches safety limit ($> 8.0^\circ\text{C}$ or $< 2.0^\circ\text{C}$).

### How to Run Risk Detection
```bash
python risk_detection.py
```

Optional CLI parameters:
```bash
python risk_detection.py --safe-min 2.0 --safe-max 8.0 --trend-window 4 --min-rise 0.4
```

### Phase 4 Outputs
* **`data/processed/risk_predictions.csv`**: Full risk evaluation log with `Timestamp`, `Actual_Temperature`, `Predicted_Temperature`, `Temperature_Trend`, `Risk_Level`, and `Alert_Message`.
* **`models/risk_detection_plot.png`**: Comprehensive visualization showing actual vs predicted temperatures and color-coded EARLY WARNING and WARNING events.
* **`models/risk_summary.json`**: Audit report with risk category breakdowns, trend counts, and sample cases.

---

## Phase 5.1: Real-Time FastAPI & WebSocket Backend

Implements the live streaming backend architecture:
$$\text{Live IoT Simulator} \longrightarrow \text{FastAPI} \longrightarrow \text{LSTM Model} \longrightarrow \text{Risk Detection} \longrightarrow \text{WebSocket (/ws/live)}$$

### Endpoints
* **`GET /api/health`**: Verifies service status.
* **`GET /docs`**: Interactive Swagger documentation.
* **`WebSocket /ws/live`**: Real-time telemetry, LSTM prediction, and early warning stream (every 1.2s).

### How to Run the Backend
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### How to Run Backend Verification
```bash
python test_backend.py
```

### Sample Live WebSocket Payload
```json
{
  "timestamp": "2026-09-30 21:36:53",
  "temperature": 4.87,
  "humidity": 71.9,
  "predicted_temperature": 4.96,
  "trend": "RISING",
  "risk_level": "EARLY WARNING",
  "alert": "Continuous abnormal temperature increase detected"
}
```

---

## Phase 5.2: Real-Time React + Vite Monitoring Dashboard

Implements a professional real-time monitoring interface connected to the FastAPI WebSocket stream (`ws://127.0.0.1:8000/ws/live`).

### Dashboard Features
* **Live Telemetry & Prediction Cards**:
  * **Current Temperature**: Real-time sensor reading in °C
  * **Humidity**: Chamber relative humidity percentage (%)
  * **Predicted Temperature**: Next-step prediction generated by the trained LSTM model in °C
  * **Risk Level**: Dynamic indicator for **`NORMAL`** (Green), **`EARLY WARNING`** (Amber), and **`WARNING`** (Red)
* **Live Status Section**: Displays exact timestamp, temperature trend (`RISING`, `FALLING`, `STABLE`), and alert diagnosis.
* **Dual-Stream Temperature Chart**:
  * Real-time line chart displaying both actual and predicted temperatures over the latest 45 readings.
  * Visual safety threshold lines at **8.0°C (Max Safe Limit)** and **2.0°C (Min Safe Limit)**.
* **Auto-Reconnecting WebSocket**: Shows `● Connected` / `● Disconnected` status and handles reconnections cleanly.
---

## Phase 6.1: ESP32 IoT Simulator & Sensor Ingestion API

Provides a software-based ESP32 simulator (`backend/esp32_simulator.py`) sending JSON telemetry to `POST /api/sensor`. Designed for drop-in physical ESP32 + DHT22 hardware replacement in the future.

### Architecture
$$\text{ESP32 Simulator / Node} \xrightarrow[\text{JSON}]{\text{POST /api/sensor}} \text{FastAPI} \longrightarrow \text{LSTM Model} \longrightarrow \text{Risk Engine} \longrightarrow \text{WebSocket} \longrightarrow \text{React Dashboard}$$

### Telemetry Formats

**HTTP Request (`POST /api/sensor`):**
```json
{
  "device_id": "ESP32_01",
  "timestamp": "2026-10-01 09:05:00",
  "temperature": 5.42,
  "humidity": 70.3
}
```

**HTTP Response:**
```json
{
  "device_id": "ESP32_01",
  "timestamp": "2026-10-01 09:05:00",
  "temperature": 5.42,
  "humidity": 70.3,
  "predicted_temperature": 5.58,
  "trend": "STABLE",
  "risk_level": "NORMAL",
  "alert": "Operating within safe cold-storage range"
}
```

### How to Run the Complete System (3 Terminals)

#### Terminal 1 — FastAPI Backend
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

#### Terminal 2 — Multi-Device ESP32 Sensor Simulator
```bash
python backend/esp32_simulator.py
```

#### Terminal 3 — React Dashboard
```bash
cd frontend
npm run dev
```

Open dashboard at: `http://localhost:5173/`
Swagger API docs: `http://127.0.0.1:8000/docs`

---

## Phase 6.2: Multi-Device IoT Monitoring + Historical Data Dashboard

Phase 6.2 expands the single-device system into an enterprise-grade multi-node cold-storage monitoring platform:

- **Simultaneous Multi-Node Emulation:** A single simulator managing `ESP32_01` (Stable nominal range 4.2–4.8°C), `ESP32_02` (Gradual warming excursion testing), and `ESP32_03` (Cooling duty cycles 3.2–5.2°C).
- **Device-Wise LSTM Buffers:** Isolated 10-reading rolling sequence buffers ensure zero cross-device reading contamination.
- **REST Endpoints Added:**
  - `GET /api/devices`: Returns active nodes with current temperatures, predictions, trends, and risk states.
  - `GET /api/devices/{device_id}/history?limit=100`: Returns chronological historical readings for a specified device from `data/live_sensor_data.csv`.
  - `GET /api/alerts?limit=20`: Returns recent `EARLY WARNING` and `WARNING` events across all devices.
- **React Dashboard Upgrades:**
  - **Device Overview Grid:** Live cards for `ESP32_01`, `ESP32_02`, and `ESP32_03` with visual risk indicators (`NORMAL`, `EARLY WARNING`, `WARNING`).
  - **Interactive Device Selector:** Switch active focus between nodes via dropdown or interactive device tabs.
  - **Isolated Historical Chart:** Telemetry chart strictly binds to the selected device with 2°C and 8°C safety lines.
  - **Active Risk Alert Panel:** Live feed of threshold exceedances and persistent warming trends.
- **Automated Multi-Device Test Suite:**
```bash
python test_multi_device.py
```

### Physical ESP32 Hardware Integration Note
This system runs as a multi-device ESP32 simulation. The software architecture and REST contracts are fully ready for physical ESP32 integration. When deploying physical microcontrollers (e.g., ESP32 + DHT22/DS18B20), program each unit with its unique `device_id` (e.g. `ESP32_01`, `ESP32_02`) to POST JSON to `/api/sensor` over Wi-Fi.

---

## Phase 6.3: Real-Time Alert & Notification System

Phase 6.3 adds an enterprise-grade real-time alert and notification system with state-transition tracking to the multi-device dashboard:

- **State-Transition Trigger Engine:** Tracks transitions per device (`NORMAL` $\to$ `EARLY WARNING`, `EARLY WARNING` $\to$ `WARNING`, and `WARNING/EARLY WARNING` $\to$ `NORMAL` recovery). Suppresses duplicate notifications when the risk state remains unchanged.
- **Floating Alert Toasts (`AlertToast.jsx`):** Non-blocking auto-dismissing toast notifications with device ID, actual vs LSTM predicted temperature, timestamp, risk badge, and manual dismiss button.
- **Alarm-Style Indicator Banner (`NotificationBanner.jsx`):** Prominent indicator at the top of the dashboard displaying global alarm status across all zones with gentle pulse animation on critical conditions.
- **Native Browser Notifications:** Uses the HTML5 Notification API with desktop alerts for `WARNING`, `EARLY WARNING`, and `RECOVERY` transitions. Gracefully degrades if disabled or unavailable.
- **Dedicated Alert History (`AlertHistory.jsx`):** Chronological log of recent alerts and recovery events with device tagging and click-to-focus capabilities.
- **Automated Alert Transition Test Suite:**
```bash
python test_phase_6_3.py
```

---

## Phase 7: Final System Status, Validation & Demonstration

### 1. Project Objective
Build an end-to-end IoT and Deep Learning monitoring system that forecasts cold-storage temperatures using an LSTM neural network and proactively alerts operators before critical food safety thresholds are breached.

### 2. System Architecture
```text
ESP32 Multi-Device Simulator (ESP32_01, ESP32_02, ESP32_03)
                     ↓  HTTP POST /api/sensor
                FastAPI Backend
                     ↓  Isolated 10-reading sequence buffers
             Pre-Trained 2-Layer LSTM Model
                     ↓  1-step ahead prediction (°C)
                 Risk Detection Engine
          (NORMAL / EARLY WARNING / WARNING / RECOVERY)
                     ↓  Broadcast & Storage
         WebSocket (/ws/live)  &  CSV (data/live_sensor_data.csv)
                     ↓
        React + Vite Interactive Dashboard
  (Overview Cards | Focused Charts | Alert Toasts | Browser Notifications | Alert History)
```

### 3. Role of the LSTM
The 2-layer LSTM (`LSTM(64) -> LSTM(32) -> Dense(1)`) acts as a one-step-ahead forward predictor. By anticipating temperature spikes before they physically breach safety thresholds, the system can issue proactive warnings rather than purely reactive alarms.

### 4. Risk Detection Rules
- **WARNING:** Predicted or current temperature $> 8.0^\circ\text{C}$ or $< 2.0^\circ\text{C}$.
- **EARLY WARNING:** Temperature is within $2.0^\circ\text{C} \le T \le 8.0^\circ\text{C}$, but 4 consecutive timesteps demonstrate persistent rising slope ($\Delta \ge 0.40^\circ\text{C}$).
- **NORMAL:** Operating safely within safe limits with stable/falling dynamics.
- **RECOVERY:** Returning from abnormal state back to `NORMAL`.

### 5. Multi-Device Simulation
- `ESP32_01`: Stable cold-storage chamber (4.2°C – 4.8°C).
- `ESP32_02`: Periodic gradual warming excursion past 8.0°C followed by emergency refrigeration recovery.
- `ESP32_03`: Standard thermostatic cooling duty cycling (3.2°C – 5.2°C).

### 6. Alert System
- Floating temporary toasts (`AlertToast.jsx`) with actual vs predicted values.
- Alarm-style dashboard indicator banner (`NotificationBanner.jsx`).
- Native HTML5 browser desktop notifications.
- State-transition duplicate suppression.
- Dedicated 20-event alert and recovery history log (`AlertHistory.jsx`).

### 7. Current Hardware Status
**CURRENT HARDWARE STATUS:**  
The current prototype uses software-simulated ESP32 devices.  
There are currently no three physical ESP32 boards connected.  
`ESP32_01`, `ESP32_02`, and `ESP32_03` are simulated device IDs used to validate the multi-device architecture.

**FUTURE HARDWARE:**  
Physical ESP32 microcontrollers with temperature/humidity sensors (e.g. DHT22 or DS18B20) can send the identical JSON payload to:  
`POST /api/sensor`  
No major backend or model architecture change is required.

### 8. How to Run the Complete Project

#### Terminal 1 — Backend API Server
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

#### Terminal 2 — Multi-Device Sensor Simulator
```bash
python backend/esp32_simulator.py
```

#### Terminal 3 — React Dashboard
```bash
cd frontend
npm run dev
```

Open application: `http://localhost:5173/`  
Swagger API docs: `http://127.0.0.1:8000/docs`

### 9. Validation Test Commands
```bash
# Phase 6.2 Multi-device test
python test_multi_device.py

# Phase 6.3 State transition & alert test
python test_phase_6_3.py

# Phase 7 Final integration test
python test_phase_7.py
```

### 10. Final Model & Evaluation Results
- **Dataset:** 1,200 time-series observations, 1,190 sequence pairs (Window: 10).
- **Split:** 810 Train (68.1%), 142 Validation (11.9%), 238 Test (20.0%).
- **Epochs:** 60.
- **Test Set MAE:** `0.1577°C` (approx 0.163°C).
- **Test Set RMSE:** `0.2151°C` (approx 0.215°C).
- **Final Validation Status:** 9/9 Integration Tests Passed (100%).

### 11. Important Project Limitations
1. Telemetry is software simulated using thermodynamic drift algorithms.
2. No physical ESP32 hardware or real cold-storage chamber is connected.
3. The dashboard does not measure the ambient physical room temperature.
4. The LSTM model is pre-trained and operates in inference mode.
5. Operating thresholds (2.0°C – 8.0°C) are defined cold-storage criteria.
6. Desktop browser notifications depend on user granting permission.








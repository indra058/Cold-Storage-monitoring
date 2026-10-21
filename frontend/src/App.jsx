import React, { useState, useEffect, useRef, useCallback } from 'react';
import MetricCard from './components/MetricCard';
import RiskCard from './components/RiskCard';
import TemperatureChart from './components/TemperatureChart';
import DeviceOverviewCard from './components/DeviceOverviewCard';
import ActiveAlertsPanel from './components/ActiveAlertsPanel';
import NotificationBanner from './components/NotificationBanner';
import AlertToast from './components/AlertToast';
import AlertHistory from './components/AlertHistory';
import './App.css';

const API_BASE = 'http://127.0.0.1:8000';
const WS_URL = 'ws://127.0.0.1:8000/ws/live';
const DEFAULT_DEVICES = ['ESP32_01', 'ESP32_02', 'ESP32_03'];
const MAX_HISTORY_POINTS = 50;

export default function App() {
  const [selectedDevice, setSelectedDevice] = useState('ESP32_01');
  const [devicesState, setDevicesState] = useState({});
  const [deviceHistories, setDeviceHistories] = useState({});
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [alertHistory, setAlertHistory] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [notificationPermission, setNotificationPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window
      ? window.Notification.permission
      : 'denied'
  );

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  // Track previous risk state per device for transition detection & duplicate prevention
  const devicePrevRisk = useRef({});

  // Helper to trigger native browser desktop notification
  const triggerBrowserNotification = useCallback(({ title, body }) => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      if (window.Notification.permission === 'granted') {
        try {
          new window.Notification(title, {
            body,
            icon: '/favicon.ico',
          });
        } catch (e) {
          console.warn('[Notification Error]', e);
        }
      }
    }
  }, []);

  // Request browser notification permission
  const requestNotificationPermission = useCallback(async () => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      try {
        const perm = await window.Notification.requestPermission();
        setNotificationPermission(perm);
        if (perm === 'granted') {
          triggerBrowserNotification({
            title: '🔔 Desktop Notifications Active',
            body: 'Cold-Storage IoT alert notifications are now enabled.',
          });
        }
      } catch (err) {
        console.warn('[Permission Request Error]', err);
      }
    }
  }, [triggerBrowserNotification]);

  // Dismiss toast handler
  const handleDismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Load initial devices list & status
  const fetchDevices = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/devices`);
      if (resp.ok) {
        const data = await resp.json();
        const map = {};
        data.forEach((d) => {
          map[d.device_id] = d;
          // Seed previous risk state
          devicePrevRisk.current[d.device_id] = d.risk_level || 'NORMAL';
        });
        setDevicesState((prev) => ({ ...prev, ...map }));
      }
    } catch (err) {
      console.warn('[API] Could not fetch devices:', err);
    }
  }, []);

  // Load initial active alerts & history
  const fetchAlerts = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/alerts?limit=25`);
      if (resp.ok) {
        const data = await resp.json();
        setActiveAlerts(data);
        setAlertHistory(data);
      }
    } catch (err) {
      console.warn('[API] Could not fetch alerts:', err);
    }
  }, []);

  // Load history for a given device
  const fetchHistoryForDevice = useCallback(async (deviceId) => {
    try {
      const resp = await fetch(`${API_BASE}/api/devices/${deviceId}/history?limit=${MAX_HISTORY_POINTS}`);
      if (resp.ok) {
        const records = await resp.json();
        setDeviceHistories((prev) => ({
          ...prev,
          [deviceId]: records,
        }));
      }
    } catch (err) {
      console.warn(`[API] Could not fetch history for ${deviceId}:`, err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchDevices();
    fetchAlerts();
    DEFAULT_DEVICES.forEach((d) => fetchHistoryForDevice(d));
  }, [fetchDevices, fetchAlerts, fetchHistoryForDevice]);

  // When selectedDevice changes, ensure its history is loaded
  useEffect(() => {
    if (!deviceHistories[selectedDevice] || deviceHistories[selectedDevice].length === 0) {
      fetchHistoryForDevice(selectedDevice);
    }
  }, [selectedDevice, deviceHistories, fetchHistoryForDevice]);

  // WebSocket Connection & Real-Time Transition Engine
  useEffect(() => {
    let isComponentMounted = true;

    function connectWebSocket() {
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (_) {}
      }

      console.log(`[WebSocket] Connecting to ${WS_URL}...`);
      const socket = new WebSocket(WS_URL);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!isComponentMounted) return;
        console.log('[WebSocket] Connected successfully');
        setIsConnected(true);
        setConnectionError(null);
      };

      socket.onmessage = (event) => {
        if (!isComponentMounted) return;
        try {
          const payload = JSON.parse(event.data);
          const devId = payload.device_id || 'ESP32_01';
          const curRisk = payload.risk_level || 'NORMAL';
          const prevRisk = devicePrevRisk.current[devId] || 'NORMAL';

          // Update multi-device state
          setDevicesState((prev) => ({
            ...prev,
            [devId]: payload,
          }));

          // Append to device-specific history without mixing
          setDeviceHistories((prev) => {
            const currentHistory = prev[devId] || [];
            const nextHistory = [...currentHistory, payload];
            return {
              ...prev,
              [devId]:
                nextHistory.length > MAX_HISTORY_POINTS
                  ? nextHistory.slice(nextHistory.length - MAX_HISTORY_POINTS)
                  : nextHistory,
            };
          });

          // ========================================================
          // PHASE 6.3: STATE-TRANSITION ALERT & NOTIFICATION ENGINE
          // ========================================================
          if (prevRisk !== curRisk) {
            devicePrevRisk.current[devId] = curRisk;

            // CASE 1: TRANSITION TO EARLY WARNING
            if (curRisk === 'EARLY WARNING') {
              const newToast = {
                id: `${devId}-${Date.now()}`,
                type: 'EARLY WARNING',
                deviceId: devId,
                timestamp: payload.timestamp,
                actualTemp: payload.temperature,
                predTemp: payload.predicted_temperature,
                message: payload.alert || 'Continuous abnormal temperature increase detected',
              };
              setToasts((prev) => [newToast, ...prev.slice(0, 4)]);

              triggerBrowserNotification({
                title: '⚠️ Cold Storage Early Warning',
                body: `${devId}: Continuous temperature rise detected. Actual: ${payload.temperature}°C, Predicted: ${payload.predicted_temperature}°C.`,
              });

              const eventRecord = {
                device_id: devId,
                timestamp: payload.timestamp,
                temperature: payload.temperature,
                predicted_temperature: payload.predicted_temperature,
                risk_level: 'EARLY WARNING',
                alert: payload.alert || 'Continuous abnormal temperature increase detected',
              };
              setAlertHistory((prev) => [eventRecord, ...prev.slice(0, 49)]);
              setActiveAlerts((prev) => [eventRecord, ...prev.slice(0, 29)]);
            }

            // CASE 2: TRANSITION TO WARNING
            else if (curRisk === 'WARNING') {
              const newToast = {
                id: `${devId}-${Date.now()}`,
                type: 'WARNING',
                deviceId: devId,
                timestamp: payload.timestamp,
                actualTemp: payload.temperature,
                predTemp: payload.predicted_temperature,
                message: payload.alert || 'Temperature exceeded safe upper threshold',
              };
              setToasts((prev) => [newToast, ...prev.slice(0, 4)]);

              triggerBrowserNotification({
                title: '🚨 Cold Storage Temperature Warning',
                body: `${devId}: Temperature reached ${payload.temperature}°C. Predicted: ${payload.predicted_temperature}°C.`,
              });

              const eventRecord = {
                device_id: devId,
                timestamp: payload.timestamp,
                temperature: payload.temperature,
                predicted_temperature: payload.predicted_temperature,
                risk_level: 'WARNING',
                alert: payload.alert || 'Temperature exceeded safe upper threshold',
              };
              setAlertHistory((prev) => [eventRecord, ...prev.slice(0, 49)]);
              setActiveAlerts((prev) => [eventRecord, ...prev.slice(0, 29)]);
            }

            // CASE 3: TRANSITION TO NORMAL (RECOVERY)
            else if (curRisk === 'NORMAL' && (prevRisk === 'EARLY WARNING' || prevRisk === 'WARNING')) {
              const recoveryToast = {
                id: `${devId}-${Date.now()}`,
                type: 'RECOVERY',
                deviceId: devId,
                timestamp: payload.timestamp,
                actualTemp: payload.temperature,
                predTemp: payload.predicted_temperature,
                message: 'Temperature has returned to the safe cold-storage range.',
              };
              setToasts((prev) => [recoveryToast, ...prev.slice(0, 4)]);

              triggerBrowserNotification({
                title: '✅ Storage Recovered',
                body: `${devId}: Temperature has returned to safe range (${payload.temperature}°C).`,
              });

              const recoveryRecord = {
                device_id: devId,
                timestamp: payload.timestamp,
                temperature: payload.temperature,
                predicted_temperature: payload.predicted_temperature,
                risk_level: 'RECOVERY',
                alert: 'Temperature returned to safe cold-storage range',
              };
              setAlertHistory((prev) => [recoveryRecord, ...prev.slice(0, 49)]);
            }
          }
        } catch (err) {
          console.error('[WebSocket] Error processing message:', err);
        }
      };

      socket.onclose = () => {
        if (!isComponentMounted) return;
        console.warn('[WebSocket] Connection closed. Attempting reconnect in 3s...');
        setIsConnected(false);
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isComponentMounted) connectWebSocket();
        }, 3000);
      };

      socket.onerror = (err) => {
        if (!isComponentMounted) return;
        console.error('[WebSocket] Socket error:', err);
        setConnectionError('Live telemetry stream unavailable. Ensure backend is running.');
      };
    }

    connectWebSocket();

    return () => {
      isComponentMounted = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [triggerBrowserNotification]);

  // Active device telemetry data
  const activeDeviceData = devicesState[selectedDevice] || {
    device_id: selectedDevice,
    temperature: null,
    humidity: null,
    predicted_temperature: null,
    trend: 'STABLE',
    risk_level: 'NORMAL',
    alert: 'Connecting to multi-device sensor stream...',
    timestamp: '--:--:--',
  };

  const activeHistory = deviceHistories[selectedDevice] || [];

  return (
    <div className="dashboard-container">
      {/* Floating Alert Toasts (Top Right) */}
      <AlertToast toasts={toasts} onDismiss={handleDismissToast} />

      {/* TOP: Header */}
      <header className="dashboard-header">
        <div className="header-branding">
          <div className="title-row">
            <span className="logo-icon">❄️</span>
            <h1 className="dashboard-title">IoT-Based Cold-Storage Monitoring</h1>
            <span className="phase-pill">PHASE 6.3</span>
          </div>
          <p className="dashboard-subtitle">
            Multi-Device ESP32 Simulation • Real-Time Alert & Notification System • LSTM Forecasting
          </p>
        </div>

        {/* Header Controls: Device Selector & Connection status */}
        <div className="header-status-area">
          <div className="device-selector-wrapper">
            <label htmlFor="device-select" className="device-select-label">
              Device:
            </label>
            <div className="custom-select-container">
              <select
                id="device-select"
                className="device-select-dropdown font-mono"
                value={selectedDevice}
                onChange={(e) => setSelectedDevice(e.target.value)}
              >
                {DEFAULT_DEVICES.map((dev) => (
                  <option key={dev} value={dev}>
                    {dev}
                  </option>
                ))}
              </select>
              <span className="select-arrow">▼</span>
            </div>
          </div>

          <div className={`connection-badge ${isConnected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot"></span>
            <span className="status-label">
              {isConnected ? '● Connected' : '● Disconnected'}
            </span>
          </div>
          <span className="server-url">127.0.0.1:8000</span>
        </div>
      </header>

      {/* TOP: Safety Reference Banner */}
      <div className="safety-banner">
        <div className="safety-rule">
          <span className="badge-safe">2.0°C</span>
          <span className="safety-text">Lower Safety Threshold</span>
        </div>
        <div className="safety-divider"></div>
        <div className="safety-rule">
          <span className="badge-safe">8.0°C</span>
          <span className="safety-text">Upper Safety Threshold</span>
        </div>
        <div className="safety-divider"></div>
        <div className="safety-rule rule-note">
          <span className="badge-info">LSTM Forecast</span>
          <span className="safety-text">Proactive Early Warning on Rising Excursions (slope ≥ 0.40°C)</span>
        </div>
        <div className="safety-divider"></div>
        <div className="safety-rule">
          <span className="badge-architecture">Ready for Hardware</span>
          <span className="safety-text">Ready for future physical ESP32 deployment</span>
        </div>
      </div>

      {/* TOP: Global Alarm-Style Indicator Banner */}
      <NotificationBanner
        devices={devicesState}
        notificationPermission={notificationPermission}
        onRequestPermission={requestNotificationPermission}
      />

      {/* MIDDLE: Device Overview Grid */}
      <section className="device-overview-section">
        <div className="section-header-row">
          <div>
            <h2 className="section-heading">Device Overview</h2>
            <p className="section-subheading">
              Real-time multi-node status. Click any device card to focus its live charts and telemetry.
            </p>
          </div>
          <div className="device-tabs">
            {DEFAULT_DEVICES.map((d) => (
              <button
                key={d}
                type="button"
                className={`device-tab-btn ${selectedDevice === d ? 'active' : ''}`}
                onClick={() => setSelectedDevice(d)}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        <div className="device-overview-grid">
          {DEFAULT_DEVICES.map((devId) => (
            <DeviceOverviewCard
              key={devId}
              deviceId={devId}
              deviceData={devicesState[devId]}
              isSelected={selectedDevice === devId}
              onSelect={setSelectedDevice}
            />
          ))}
        </div>
      </section>

      {/* NEXT: Focused Device Detail Metrics */}
      <section className="selected-device-section">
        <div className="selected-device-banner">
          <div className="selected-device-info">
            <span className="focus-label">FOCUSED NODE</span>
            <h2 className="selected-device-title font-mono">{selectedDevice}</h2>
            <span className="focus-zone">
              {selectedDevice === 'ESP32_01'
                ? 'Zone A • Stable Storage (4.2°C – 4.8°C)'
                : selectedDevice === 'ESP32_02'
                ? 'Zone B • Warming Excursions Test'
                : 'Zone C • Cooling Duty Cycling (3.2°C – 5.2°C)'}
            </span>
          </div>
          <div className="selected-device-actions">
            <span className="data-points-count font-mono">
              {activeHistory.length} Historical Points Loaded
            </span>
          </div>
        </div>

        {/* 4 Telemetry & Prediction Cards */}
        <div className="cards-grid">
          <MetricCard
            title="Current Temperature"
            value={
              activeDeviceData.temperature !== null && activeDeviceData.temperature !== undefined
                ? Number(activeDeviceData.temperature).toFixed(2)
                : '--'
            }
            unit="°C"
            subtitle={`${selectedDevice} Sensor Reading`}
            accentColor="#06b6d4"
            icon="🌡️"
          />

          <MetricCard
            title="Humidity"
            value={
              activeDeviceData.humidity !== null && activeDeviceData.humidity !== undefined
                ? Number(activeDeviceData.humidity).toFixed(1)
                : '--'
            }
            unit="%"
            subtitle="Chamber Relative Humidity"
            accentColor="#3b82f6"
            icon="💧"
          />

          <MetricCard
            title="Predicted Temperature"
            value={
              activeDeviceData.predicted_temperature !== null &&
              activeDeviceData.predicted_temperature !== undefined
                ? Number(activeDeviceData.predicted_temperature).toFixed(2)
                : '--'
            }
            unit="°C"
            subtitle="LSTM 1-Step Ahead Forecast"
            accentColor="#a855f7"
            icon="🧠"
          />

          <RiskCard
            riskLevel={activeDeviceData.risk_level}
            alertMessage={activeDeviceData.alert}
          />
        </div>

        {/* Telemetry Status Strip */}
        <div className="live-status-section">
          <div className="live-status-card">
            <div className="status-col">
              <span className="col-label">Device:</span>
              <span className="col-val font-mono">{selectedDevice}</span>
            </div>

            <div className="status-col">
              <span className="col-label">Last Updated:</span>
              <span className="col-val font-mono">
                {activeDeviceData.timestamp || 'Waiting for live data...'}
              </span>
            </div>

            <div className="status-col">
              <span className="col-label">Trend:</span>
              <span
                className={`col-val trend-pill trend-${(activeDeviceData.trend || 'STABLE')
                  .toLowerCase()
                  .replace(/\s+/g, '-')}`}
              >
                {activeDeviceData.trend || 'STABLE'}
              </span>
            </div>

            <div className="status-col col-alert">
              <span className="col-label">Alert:</span>
              <span className="col-val alert-message">
                {activeDeviceData.alert || 'Operating within safe cold-storage range'}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* NEXT: Historical Temperature Chart */}
      <section className="chart-section">
        <TemperatureChart data={activeHistory} deviceId={selectedDevice} />
      </section>

      {/* NEXT: Active Alerts Panel */}
      <section className="alerts-section">
        <ActiveAlertsPanel alerts={activeAlerts} onSelectDevice={setSelectedDevice} />
      </section>

      {/* BOTTOM: Dedicated Alert History */}
      <section className="alert-history-section">
        <AlertHistory history={alertHistory} onSelectDevice={setSelectedDevice} />
      </section>

      {/* Footer */}
      <footer className="dashboard-footer">
        <div className="footer-left">
          <span>Cold Storage IoT & DNN Monitoring System • Phase 6.3</span>
          <span className="footer-dot">•</span>
          <span>Multi-device ESP32 simulation — Ready for future physical ESP32 deployment</span>
        </div>
        <div className="footer-right">
          <span>Real-Time Alert State Engine • Native Browser Notifications</span>
        </div>
      </footer>
    </div>
  );
}

import React from 'react';

export default function NotificationBanner({
  devices = {},
  notificationPermission,
  onRequestPermission,
}) {
  // Determine highest global alarm level across all monitored devices
  const deviceList = Object.values(devices);
  const warningDevice = deviceList.find((d) => d.risk_level === 'WARNING');
  const earlyWarningDevice = deviceList.find((d) => d.risk_level === 'EARLY WARNING');

  let alarmState = 'NORMAL';
  let alarmMessage = 'All storage zones operating normally (Safe range: 2.0°C – 8.0°C)';
  let alarmIcon = '🛡️';
  let affectedDevice = null;

  if (warningDevice) {
    alarmState = 'WARNING';
    alarmIcon = '🚨';
    affectedDevice = warningDevice.device_id;
    alarmMessage = `Critical temperature warning in ${warningDevice.device_id} (${Number(warningDevice.temperature).toFixed(2)}°C)`;
  } else if (earlyWarningDevice) {
    alarmState = 'EARLY WARNING';
    alarmIcon = '⚠️';
    affectedDevice = earlyWarningDevice.device_id;
    alarmMessage = `Persistent temperature rise detected in ${earlyWarningDevice.device_id} (LSTM forecast: ${Number(earlyWarningDevice.predicted_temperature).toFixed(2)}°C)`;
  }

  const alarmClass = `alarm-${alarmState.toLowerCase().replace(/\s+/g, '-')}`;

  return (
    <div className={`alarm-indicator-banner ${alarmClass}`}>
      <div className="alarm-content-left">
        <span className="alarm-icon">{alarmIcon}</span>
        <div className="alarm-text-block">
          <div className="alarm-title-row">
            <span className="alarm-state-tag">{alarmState}</span>
            {affectedDevice && (
              <span className="alarm-device-pill font-mono">{affectedDevice}</span>
            )}
          </div>
          <span className="alarm-desc">{alarmMessage}</span>
        </div>
      </div>

      <div className="alarm-controls-right">
        {/* Browser Notification Permission Button */}
        {notificationPermission === 'granted' ? (
          <span className="notif-btn notif-btn-active" title="Browser desktop notifications active">
            🔔 Desktop Alerts Active
          </span>
        ) : notificationPermission === 'denied' ? (
          <span className="notif-btn notif-btn-disabled" title="Browser notifications blocked in browser settings">
            🔕 Alerts Blocked
          </span>
        ) : (
          <button
            type="button"
            className="notif-btn notif-btn-action"
            onClick={onRequestPermission}
            title="Click to enable browser desktop notifications"
          >
            🔔 Enable Desktop Alerts
          </button>
        )}
      </div>
    </div>
  );
}

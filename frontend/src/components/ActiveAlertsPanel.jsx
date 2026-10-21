import React from 'react';

export default function ActiveAlertsPanel({ alerts = [], onSelectDevice }) {
  return (
    <div className="alerts-card">
      <div className="alerts-header">
        <div className="alerts-title-group">
          <span className="alerts-icon">🚨</span>
          <h3 className="alerts-title">Active Risk Alerts</h3>
          <span className="alerts-badge-count">
            {alerts.length} {alerts.length === 1 ? 'alert' : 'alerts'}
          </span>
        </div>
        <span className="alerts-subtitle">
          Real-time abnormal temperature excursion & rising trend events
        </span>
      </div>

      <div className="alerts-body">
        {alerts.length === 0 ? (
          <div className="no-alerts-state">
            <span className="no-alerts-icon">🛡️</span>
            <div className="no-alerts-text">
              <strong>No active alerts</strong>
              <p>All connected cold-storage nodes are operating within normal parameters.</p>
            </div>
          </div>
        ) : (
          <div className="alerts-table-wrapper">
            <table className="alerts-table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Time</th>
                  <th>Current Temp</th>
                  <th>Predicted</th>
                  <th>Risk Level</th>
                  <th>Alert Details</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((item, idx) => {
                  const riskCls = (item.risk_level || 'NORMAL')
                    .toLowerCase()
                    .replace(/\s+/g, '-');
                  const timeStr = item.timestamp
                    ? item.timestamp.includes(' ')
                      ? item.timestamp.split(' ')[1]
                      : item.timestamp
                    : '--';

                  return (
                    <tr
                      key={`${item.device_id}-${item.timestamp}-${idx}`}
                      className={`alert-row alert-row-${riskCls}`}
                      onClick={() => onSelectDevice && onSelectDevice(item.device_id)}
                      title={`Click to view ${item.device_id}`}
                    >
                      <td>
                        <span className="alert-device-tag font-mono">
                          {item.device_id}
                        </span>
                      </td>
                      <td className="font-mono text-dim">{timeStr}</td>
                      <td>
                        <span className="temp-val-alert font-mono">
                          {item.temperature !== undefined ? `${Number(item.temperature).toFixed(2)} °C` : '--'}
                        </span>
                      </td>
                      <td>
                        <span className="pred-val-alert font-mono">
                          {item.predicted_temperature !== undefined ? `${Number(item.predicted_temperature).toFixed(2)} °C` : '--'}
                        </span>
                      </td>
                      <td>
                        <span className={`risk-pill risk-pill-${riskCls}`}>
                          {item.risk_level}
                        </span>
                      </td>
                      <td className="alert-desc-col">
                        {item.alert || 'Abnormal condition detected'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

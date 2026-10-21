import React from 'react';

export default function AlertHistory({ history = [], onSelectDevice }) {
  const displayRecords = history.slice(0, 20);

  return (
    <div className="alert-history-card">
      <div className="alert-history-header">
        <div className="history-title-group">
          <span className="history-icon">📜</span>
          <h3 className="history-title">Alert & Event History</h3>
          <span className="history-count-badge font-mono">
            {displayRecords.length} Events Logged
          </span>
        </div>
        <p className="history-subtitle">
          Chronological record of recent temperature excursions, LSTM rising alerts, and recovery events.
        </p>
      </div>

      <div className="alert-history-body">
        {displayRecords.length === 0 ? (
          <div className="empty-history-state">
            <span className="empty-icon">🛡️</span>
            <p>No historical alert events recorded. Cold storage operating nominally.</p>
          </div>
        ) : (
          <div className="history-table-container">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Date & Time</th>
                  <th>Actual Temp</th>
                  <th>Predicted Temp</th>
                  <th>Risk Level</th>
                  <th>Alert Details</th>
                </tr>
              </thead>
              <tbody>
                {displayRecords.map((item, idx) => {
                  const risk = (item.risk_level || 'NORMAL').toUpperCase();
                  const riskCls = risk.toLowerCase().replace(/\s+/g, '-');
                  const isRecovery = risk === 'RECOVERY' || risk.includes('RECOVER');

                  return (
                    <tr
                      key={`${item.device_id}-${item.timestamp}-${idx}`}
                      className={`history-row history-row-${riskCls} ${isRecovery ? 'history-row-recovery' : ''}`}
                      onClick={() => onSelectDevice && onSelectDevice(item.device_id)}
                      title={`Click to focus ${item.device_id}`}
                    >
                      <td>
                        <span className="history-device-tag font-mono">
                          {item.device_id}
                        </span>
                      </td>
                      <td className="font-mono history-time-col">
                        {item.timestamp || '--'}
                      </td>
                      <td>
                        <span className="history-temp-val font-mono">
                          {item.temperature !== undefined && item.temperature !== null
                            ? `${Number(item.temperature).toFixed(2)} °C`
                            : '--'}
                        </span>
                      </td>
                      <td>
                        <span className="history-pred-val font-mono">
                          {item.predicted_temperature !== undefined && item.predicted_temperature !== null
                            ? `${Number(item.predicted_temperature).toFixed(2)} °C`
                            : '--'}
                        </span>
                      </td>
                      <td>
                        <span className={`risk-pill risk-pill-${riskCls}`}>
                          {isRecovery ? 'RECOVERED' : risk}
                        </span>
                      </td>
                      <td className="history-msg-col">
                        {item.alert || 'Operating within safe cold-storage range'}
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

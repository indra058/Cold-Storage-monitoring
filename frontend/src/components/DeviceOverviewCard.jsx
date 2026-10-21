import React from 'react';

export default function DeviceOverviewCard({
  deviceId,
  deviceData,
  isSelected,
  onSelect,
}) {
  const data = deviceData || {};
  const risk = (data.risk_level || 'NORMAL').toUpperCase();
  const trend = (data.trend || 'STABLE').toUpperCase();

  let riskClass = 'risk-normal';
  let riskBadgeCls = 'badge-normal';
  if (risk === 'EARLY WARNING') {
    riskClass = 'risk-early-warning';
    riskBadgeCls = 'badge-early-warning';
  } else if (risk === 'WARNING') {
    riskClass = 'risk-warning';
    riskBadgeCls = 'badge-warning';
  }

  const timeStr = data.timestamp
    ? data.timestamp.includes(' ')
      ? data.timestamp.split(' ')[1]
      : data.timestamp
    : '--:--:--';

  return (
    <div
      className={`device-overview-card ${riskClass} ${isSelected ? 'selected' : ''}`}
      onClick={() => onSelect(deviceId)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onSelect(deviceId);
      }}
    >
      <div className="doc-header">
        <div className="doc-title-row">
          <span className="doc-icon">📡</span>
          <span className="doc-id font-mono">{deviceId}</span>
          {isSelected && <span className="doc-active-pill">ACTIVE</span>}
        </div>
        <span className={`doc-risk-badge ${riskBadgeCls}`}>{risk}</span>
      </div>

      <div className="doc-metrics-row">
        <div className="doc-metric">
          <span className="doc-metric-label">Temp</span>
          <span className="doc-metric-value temp font-mono">
            {data.temperature !== undefined ? `${Number(data.temperature).toFixed(2)}°C` : '--'}
          </span>
        </div>

        <div className="doc-metric">
          <span className="doc-metric-label">Humidity</span>
          <span className="doc-metric-value hum font-mono">
            {data.humidity !== undefined ? `${Number(data.humidity).toFixed(1)}%` : '--'}
          </span>
        </div>

        <div className="doc-metric">
          <span className="doc-metric-label">LSTM Pred</span>
          <span className="doc-metric-value pred font-mono">
            {data.predicted_temperature !== undefined ? `${Number(data.predicted_temperature).toFixed(2)}°C` : '--'}
          </span>
        </div>
      </div>

      <div className="doc-footer">
        <div className="doc-trend-group">
          <span className="doc-footer-label">Trend:</span>
          <span className={`trend-pill trend-${trend.toLowerCase().replace(/\s+/g, '-')}`}>
            {trend}
          </span>
        </div>
        <div className="doc-time-group">
          <span className="doc-footer-label">Updated:</span>
          <span className="doc-time-val font-mono">{timeStr}</span>
        </div>
      </div>
    </div>
  );
}

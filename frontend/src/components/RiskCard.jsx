import React from 'react';

export default function RiskCard({ riskLevel, alertMessage }) {
  // Normalize key for CSS classes
  const level = (riskLevel || 'NORMAL').toUpperCase();
  
  let statusClass = 'risk-normal';
  let badgeText = 'NORMAL';
  let statusIcon = '✓';
  let defaultDesc = 'Operating within safe cold-storage range';

  if (level === 'EARLY WARNING') {
    statusClass = 'risk-early-warning';
    badgeText = 'EARLY WARNING';
    statusIcon = '⚠';
    defaultDesc = 'Continuous abnormal temperature increase detected';
  } else if (level === 'WARNING') {
    statusClass = 'risk-warning';
    badgeText = 'WARNING';
    statusIcon = '🚨';
    defaultDesc = 'Temperature exceeded safe upper threshold';
  }

  return (
    <div className={`metric-card risk-card ${statusClass}`}>
      <div className="metric-header">
        <span className="metric-title">Risk Level</span>
        <span className="risk-indicator-dot"></span>
      </div>

      <div className="risk-badge-container">
        <span className="risk-icon">{statusIcon}</span>
        <span className="risk-level-text">{badgeText}</span>
      </div>

      <div className="risk-alert-desc">
        {alertMessage || defaultDesc}
      </div>
    </div>
  );
}

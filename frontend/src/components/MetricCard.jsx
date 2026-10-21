import React from 'react';

export default function MetricCard({ title, value, unit, subtitle, accentColor, icon }) {
  return (
    <div 
      className="metric-card" 
      style={{ '--card-accent': accentColor || 'var(--color-cyan)' }}
    >
      <div className="metric-header">
        <span className="metric-title">{title}</span>
        {icon && <span className="metric-icon">{icon}</span>}
      </div>
      <div className="metric-value-container">
        <span className="metric-value">
          {value !== null && value !== undefined ? value : '--'}
        </span>
        {unit && <span className="metric-unit">{unit}</span>}
      </div>
      {subtitle && <div className="metric-subtitle">{subtitle}</div>}
    </div>
  );
}

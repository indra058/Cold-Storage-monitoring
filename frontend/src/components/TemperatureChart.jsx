import React, { useMemo, useState } from 'react';

export default function TemperatureChart({ data = [], deviceId = 'ESP32_01' }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  // SVG dimensions
  const svgWidth = 840;
  const svgHeight = 320;
  const margin = { top: 25, right: 35, bottom: 45, left: 55 };
  const chartWidth = svgWidth - margin.left - margin.right;
  const chartHeight = svgHeight - margin.top - margin.bottom;

  // Calculate dynamic scale bounds
  const { minY, maxY, pointsActual, pointsPred, timeLabels, yTicks } = useMemo(() => {
    if (!data || data.length === 0) {
      return { minY: 0, maxY: 10, pointsActual: [], pointsPred: [], timeLabels: [], yTicks: [2, 4, 6, 8, 10] };
    }

    const actuals = data.map(d => Number(d.temperature) || 0);
    const preds = data.map(d => Number(d.predicted_temperature) || 0);
    const allTemps = [...actuals, ...preds];

    // Guarantee 2°C and 8°C are visible within scale
    const rawMin = Math.min(...allTemps, 2.0);
    const rawMax = Math.max(...allTemps, 8.0);

    const calculatedMin = Math.floor(rawMin - 0.5);
    const calculatedMax = Math.ceil(rawMax + 0.8);

    const yRange = calculatedMax - calculatedMin || 1;

    const getX = (idx) => {
      if (data.length <= 1) return margin.left;
      return margin.left + (idx / (data.length - 1)) * chartWidth;
    };

    const getY = (val) => {
      const clamped = Math.max(calculatedMin, Math.min(calculatedMax, val));
      const normalized = (clamped - calculatedMin) / yRange;
      return margin.top + chartHeight - normalized * chartHeight;
    };

    const pActual = data.map((d, i) => ({
      x: getX(i),
      y: getY(Number(d.temperature)),
      val: Number(d.temperature),
      time: d.timestamp ? d.timestamp.split(' ')[1] || d.timestamp : '',
    }));

    const pPred = data.map((d, i) => ({
      x: getX(i),
      y: getY(Number(d.predicted_temperature)),
      val: Number(d.predicted_temperature),
      time: d.timestamp ? d.timestamp.split(' ')[1] || d.timestamp : '',
    }));

    // Y ticks at 2°C intervals
    const ticks = [];
    for (let t = Math.ceil(calculatedMin / 2) * 2; t <= calculatedMax; t += 2) {
      ticks.push(t);
    }

    // Time labels: pick up to 5 evenly spaced labels
    const tLabels = [];
    const step = Math.max(1, Math.floor(data.length / 5));
    for (let i = 0; i < data.length; i += step) {
      const t = data[i].timestamp ? data[i].timestamp.split(' ')[1] || data[i].timestamp : '';
      tLabels.push({ x: getX(i), text: t });
    }
    // Always include the latest point
    if (data.length > 1) {
      const lastIdx = data.length - 1;
      const lastT = data[lastIdx].timestamp ? data[lastIdx].timestamp.split(' ')[1] || data[lastIdx].timestamp : '';
      if (!tLabels.some(l => Math.abs(l.x - getX(lastIdx)) < 40)) {
        tLabels.push({ x: getX(lastIdx), text: lastT });
      }
    }

    return {
      minY: calculatedMin,
      maxY: calculatedMax,
      pointsActual: pActual,
      pointsPred: pPred,
      timeLabels: tLabels,
      yTicks: ticks,
    };
  }, [data]);

  // Generate SVG path commands
  const pathActual = useMemo(() => {
    if (pointsActual.length === 0) return '';
    return pointsActual.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`, '');
  }, [pointsActual]);

  const pathPred = useMemo(() => {
    if (pointsPred.length === 0) return '';
    return pointsPred.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`, '');
  }, [pointsPred]);

  // Area under actual curve for modern subtle gradient glow
  const pathArea = useMemo(() => {
    if (pointsActual.length === 0) return '';
    const bottomY = margin.top + chartHeight;
    const firstX = pointsActual[0].x.toFixed(1);
    const lastX = pointsActual[pointsActual.length - 1].x.toFixed(1);
    return `${pathActual} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;
  }, [pathActual, pointsActual]);

  // Y coordinate for threshold lines
  const yCoord8 = useMemo(() => {
    const norm = (8.0 - minY) / (maxY - minY || 1);
    return margin.top + chartHeight - norm * chartHeight;
  }, [minY, maxY]);

  const yCoord2 = useMemo(() => {
    const norm = (2.0 - minY) / (maxY - minY || 1);
    return margin.top + chartHeight - norm * chartHeight;
  }, [minY, maxY]);

  const activePoint = hoverIndex !== null && pointsActual[hoverIndex] ? {
    actual: pointsActual[hoverIndex],
    pred: pointsPred[hoverIndex],
    raw: data[hoverIndex]
  } : (pointsActual.length > 0 ? {
    actual: pointsActual[pointsActual.length - 1],
    pred: pointsPred[pointsPred.length - 1],
    raw: data[data.length - 1]
  } : null);

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <h3 className="chart-title">
            Temperature Monitoring & Forecast <span className="chart-device-tag font-mono">{deviceId}</span>
          </h3>
          <p className="chart-subtitle">
            Telemetry history ({data.length} readings) with LSTM 1-step ahead projection for {deviceId}
          </p>
        </div>

        {/* Legend */}
        <div className="chart-legend">
          <div className="legend-item">
            <span className="legend-line line-actual"></span>
            <span>Actual Temp (°C)</span>
          </div>
          <div className="legend-item">
            <span className="legend-line line-pred"></span>
            <span>LSTM Forecast (°C)</span>
          </div>
          <div className="legend-item">
            <span className="legend-line line-threshold"></span>
            <span>8.0°C Max Safe</span>
          </div>
        </div>
      </div>

      <div className="chart-svg-container">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="telemetry-chart-svg"
          preserveAspectRatio="xMidYMid meet"
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines and Y-axis labels */}
          {yTicks.map(val => {
            const yPos = margin.top + chartHeight - ((val - minY) / (maxY - minY || 1)) * chartHeight;
            return (
              <g key={val} className="grid-line-group">
                <line
                  x1={margin.left}
                  y1={yPos}
                  x2={svgWidth - margin.right}
                  y2={yPos}
                  stroke="rgba(255, 255, 255, 0.07)"
                  strokeDasharray="3 3"
                />
                <text
                  x={margin.left - 10}
                  y={yPos + 4}
                  textAnchor="end"
                  fill="var(--text-dim)"
                  fontSize="11"
                  fontFamily="var(--font-mono)"
                >
                  {val.toFixed(1)}°
                </text>
              </g>
            );
          })}

          {/* 8.0°C Upper Safe Reference Line */}
          {yCoord8 >= margin.top && yCoord8 <= margin.top + chartHeight && (
            <g className="threshold-line-group">
              <line
                x1={margin.left}
                y1={yCoord8}
                x2={svgWidth - margin.right}
                y2={yCoord8}
                stroke="#ef4444"
                strokeWidth="1.8"
                strokeDasharray="5 4"
              />
              <rect
                x={svgWidth - margin.right - 92}
                y={yCoord8 - 18}
                width="92"
                height="16"
                rx="3"
                fill="rgba(239, 68, 68, 0.2)"
                stroke="rgba(239, 68, 68, 0.6)"
                strokeWidth="0.8"
              />
              <text
                x={svgWidth - margin.right - 46}
                y={yCoord8 - 6}
                fill="#fca5a5"
                fontSize="10"
                fontWeight="600"
                textAnchor="middle"
                fontFamily="var(--font-sans)"
              >
                8.0°C Warning
              </text>
            </g>
          )}

          {/* 2.0°C Lower Safe Reference Line */}
          {yCoord2 >= margin.top && yCoord2 <= margin.top + chartHeight && (
            <g className="threshold-line-group">
              <line
                x1={margin.left}
                y1={yCoord2}
                x2={svgWidth - margin.right}
                y2={yCoord2}
                stroke="#10b981"
                strokeWidth="1.2"
                strokeDasharray="4 4"
                opacity="0.7"
              />
              <text
                x={margin.left + 8}
                y={yCoord2 - 5}
                fill="#6ee7b7"
                fontSize="10"
                fontFamily="var(--font-sans)"
                opacity="0.85"
              >
                2.0°C Min Safe
              </text>
            </g>
          )}

          {/* Area fill */}
          {pathArea && <path d={pathArea} fill="url(#actualGradient)" />}

          {/* Actual line */}
          {pathActual && (
            <path
              d={pathActual}
              fill="none"
              stroke="#06b6d4"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Predicted line (dashed) */}
          {pathPred && (
            <path
              d={pathPred}
              fill="none"
              stroke="#a855f7"
              strokeWidth="2.2"
              strokeDasharray="5 3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Latest / Hover Highlight Circles */}
          {activePoint && (
            <g className="highlight-point">
              <line
                x1={activePoint.actual.x}
                y1={margin.top}
                x2={activePoint.actual.x}
                y2={margin.top + chartHeight}
                stroke="rgba(255, 255, 255, 0.2)"
                strokeDasharray="2 2"
              />
              {/* Actual point */}
              <circle
                cx={activePoint.actual.x}
                cy={activePoint.actual.y}
                r="5"
                fill="#06b6d4"
                stroke="#ffffff"
                strokeWidth="2"
              />
              {/* Predicted point */}
              <circle
                cx={activePoint.pred.x}
                cy={activePoint.pred.y}
                r="4.5"
                fill="#a855f7"
                stroke="#ffffff"
                strokeWidth="1.8"
              />
            </g>
          )}

          {/* X Axis Time Labels */}
          {timeLabels.map((lbl, idx) => (
            <text
              key={idx}
              x={lbl.x}
              y={svgHeight - 15}
              textAnchor="middle"
              fill="var(--text-dim)"
              fontSize="10"
              fontFamily="var(--font-mono)"
            >
              {lbl.text}
            </text>
          ))}
        </svg>
      </div>

      {/* Real-Time Callout Footer */}
      {activePoint && (
        <div className="chart-footer-stats">
          <div className="stat-pill">
            <span className="stat-label">Time:</span>
            <span className="stat-val font-mono">{activePoint.raw.timestamp || '--'}</span>
          </div>
          <div className="stat-pill">
            <span className="stat-label">Actual:</span>
            <span className="stat-val actual-color font-mono">{activePoint.raw.temperature?.toFixed(2)} °C</span>
          </div>
          <div className="stat-pill">
            <span className="stat-label">Forecast:</span>
            <span className="stat-val pred-color font-mono">{activePoint.raw.predicted_temperature?.toFixed(2)} °C</span>
          </div>
          <div className="stat-pill">
            <span className="stat-label">Diff:</span>
            <span className="stat-val font-mono">
              {(activePoint.raw.predicted_temperature - activePoint.raw.temperature >= 0 ? '+' : '')}
              {(activePoint.raw.predicted_temperature - activePoint.raw.temperature).toFixed(2)} °C
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

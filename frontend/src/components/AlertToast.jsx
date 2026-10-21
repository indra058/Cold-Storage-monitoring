import React, { useEffect } from 'react';

export default function AlertToast({ toasts = [], onDismiss }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="alert-toast-container" aria-live="assertive">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }) {
  const { id, type, deviceId, timestamp, actualTemp, predTemp, message } = toast;

  // Auto-dismiss after 7 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(id);
    }, 7000);
    return () => clearTimeout(timer);
  }, [id, onDismiss]);

  const isWarning = type === 'WARNING';
  const isEarlyWarning = type === 'EARLY WARNING';
  const isRecovery = type === 'RECOVERY';

  let toastClass = 'toast-info';
  let badgeText = type;
  let icon = 'ℹ️';

  if (isWarning) {
    toastClass = 'toast-warning';
    badgeText = 'TEMPERATURE WARNING';
    icon = '🚨';
  } else if (isEarlyWarning) {
    toastClass = 'toast-early-warning';
    badgeText = 'EARLY WARNING';
    icon = '⚠️';
  } else if (isRecovery) {
    toastClass = 'toast-recovery';
    badgeText = 'STORAGE RECOVERED';
    icon = '✅';
  }

  return (
    <div className={`alert-toast-item ${toastClass}`}>
      <div className="toast-header">
        <div className="toast-title-group">
          <span className="toast-icon">{icon}</span>
          <span className="toast-badge">{badgeText}</span>
          <span className="toast-device-tag font-mono">{deviceId}</span>
        </div>
        <button
          type="button"
          className="toast-close-btn"
          onClick={() => onDismiss(id)}
          aria-label="Close notification"
        >
          ✕
        </button>
      </div>

      <div className="toast-body">
        <div className="toast-temp-row">
          <div className="toast-temp-col">
            <span className="toast-label">Actual:</span>
            <span className="toast-val actual font-mono">
              {actualTemp !== undefined && actualTemp !== null ? `${Number(actualTemp).toFixed(2)}°C` : '--'}
            </span>
          </div>

          {!isRecovery && predTemp !== undefined && predTemp !== null && (
            <div className="toast-temp-col">
              <span className="toast-label">Predicted:</span>
              <span className="toast-val pred font-mono">
                {Number(predTemp).toFixed(2)}°C
              </span>
            </div>
          )}

          <div className="toast-temp-col time-col">
            <span className="toast-label">Time:</span>
            <span className="toast-time font-mono">{timestamp}</span>
          </div>
        </div>

        <p className="toast-message">{message}</p>
      </div>

      <div className="toast-progress-bar"></div>
    </div>
  );
}

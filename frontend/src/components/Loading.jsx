import { IconAlert, IconRefresh, IconSparkles } from './Icons'

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="spinner-wrap" role="status" aria-live="polite">
      <div className="spinner" />
      <span className="muted" style={{ fontWeight: 500, fontSize: '14px' }}>
        {label}
      </span>
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state" style={{ borderColor: 'var(--err-line)', background: 'var(--err-bg)' }}>
      <div style={{ color: 'var(--err)', marginBottom: '8px' }}>
        <IconAlert size={36} />
      </div>
      <strong style={{ color: 'var(--err-dark)' }}>Something went wrong</strong>
      <p style={{ color: 'var(--err-dark)', margin: '6px 0 14px' }}>
        {message || 'Unable to load content right now. Please try again.'}
      </p>
      {onRetry && (
        <button className="btn btn-secondary btn-sm" onClick={onRetry}>
          <IconRefresh size={14} />
          <span>Retry</span>
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, hint, children, icon = '📦' }) {
  return (
    <div className="state">
      <span className="state-icon">{icon}</span>
      <strong>{title || 'Nothing here yet'}</strong>
      {hint && <p className="muted small" style={{ margin: '6px 0 16px' }}>{hint}</p>}
      {children}
    </div>
  )
}

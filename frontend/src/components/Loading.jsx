export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="spinner-wrap" role="status" aria-live="polite">
      <div className="spinner" />
      <span className="muted">{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state state-error">
      <strong>Something went wrong</strong>
      <p>{message || 'Please try again.'}</p>
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, hint, children }) {
  return (
    <div className="state">
      <strong>{title || 'Nothing here yet'}</strong>
      {hint && <p className="muted">{hint}</p>}
      {children}
    </div>
  )
}

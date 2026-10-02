const STATUS_CLASS = {
  PENDING: 'badge-pending',
  ACCEPTED: 'badge-accepted',
  REJECTED: 'badge-rejected',
  CANCELLED: 'badge-cancelled',
  COMPLETED: 'badge-completed',
}

export function StatusBadge({ status }) {
  return <span className={`badge ${STATUS_CLASS[status] || ''}`}>{status}</span>
}

export function VerifyBadge({ status }) {
  if (status === 'VERIFIED') return <span className="badge badge-accepted">✓ Verified</span>
  if (status === 'PENDING') return <span className="badge badge-pending">Pending review</span>
  return <span className="badge badge-rejected">Rejected</span>
}

export function AvailabilityBadge({ status }) {
  return (
    <span className={`badge ${status === 'AVAILABLE' ? 'badge-accepted' : 'badge-cancelled'}`}>
      {status === 'AVAILABLE' ? '● Available' : '○ Unavailable'}
    </span>
  )
}

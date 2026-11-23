import { IconCheck, IconCheckCircle, IconClock, IconShieldCheck, IconX } from './Icons'

const STATUS_CONFIG = {
  PENDING: { className: 'badge-pending', label: 'Pending', icon: IconClock },
  ACCEPTED: { className: 'badge-accepted', label: 'Accepted', icon: IconCheckCircle },
  REJECTED: { className: 'badge-rejected', label: 'Rejected', icon: IconX },
  CANCELLED: { className: 'badge-cancelled', label: 'Cancelled', icon: IconX },
  COMPLETED: { className: 'badge-completed', label: 'Completed', icon: IconCheck },
}

export function StatusBadge({ status }) {
  const conf = STATUS_CONFIG[status] || { className: 'badge-cancelled', label: status, icon: null }
  const IconComp = conf.icon
  return (
    <span className={`badge ${conf.className}`}>
      <span className="badge-dot" />
      {IconComp && <IconComp size={12} />}
      <span>{conf.label}</span>
    </span>
  )
}

export function VerifyBadge({ status }) {
  if (status === 'VERIFIED') {
    return (
      <span className="badge badge-accepted">
        <IconShieldCheck size={13} />
        <span>Verified Expert</span>
      </span>
    )
  }
  if (status === 'PENDING') {
    return (
      <span className="badge badge-pending">
        <IconClock size={12} />
        <span>Verification Pending</span>
      </span>
    )
  }
  return (
    <span className="badge badge-rejected">
      <IconX size={12} />
      <span>Unverified</span>
    </span>
  )
}

export function AvailabilityBadge({ status }) {
  const isAvailable = status === 'AVAILABLE'
  return (
    <span className={`badge ${isAvailable ? 'badge-accepted' : 'badge-cancelled'}`}>
      <span className="badge-dot" />
      <span>{isAvailable ? 'Available Now' : 'Currently Busy'}</span>
    </span>
  )
}

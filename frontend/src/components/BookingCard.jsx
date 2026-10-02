import { StatusBadge } from './Badges'

/** Human label for a booking row. Customer sees "Expert #id", expert sees "Customer #id". */
export default function BookingCard({ booking, perspective = 'customer', actions, onAction, footer }) {
  const d = new Date(`${booking.scheduled_date}T${booking.scheduled_time}`)
  const when = isNaN(d.getTime())
    ? `${booking.scheduled_date} ${booking.scheduled_time}`
    : d.toLocaleString(undefined, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      })

  return (
    <div className="card booking-card">
      <div className="card-head">
        <div>
          <h3>{booking.service_name}</h3>
          <p className="muted small">
            Booking #{booking.id} ·{' '}
            {perspective === 'expert'
              ? `Customer #${booking.customer_id}`
              : `Expert #${booking.expert_id}`}
          </p>
        </div>
        <StatusBadge status={booking.status} />
      </div>

      <div className="card-body">
        <p>📅 {when}</p>
        <p>📍 {booking.service_address}</p>
        <p className="muted small">
          ₹{Number(booking.service_price).toFixed(2)} (rate locked at booking)
          {booking.payment_status ? (
            <span className={booking.payment_status === 'PAID' ? 'paid-tag' : 'muted'}>
              {' '}· {booking.payment_status === 'PAID' ? '✅ PAID' : booking.payment_status}
            </span>
          ) : null}
        </p>
        {booking.cancellation_reason && (
          <p className="small danger">Reason: {booking.cancellation_reason}</p>
        )}
        {booking.customer_notes && <p className="small muted">Notes: {booking.customer_notes}</p>}
      </div>

      {actions?.length > 0 && (
        <div className="card-actions">
          {actions.map((a) => (
            <button
              key={a.key}
              className={`btn btn-sm ${a.kind || 'btn-primary'}`}
              disabled={a.disabled}
              onClick={() => onAction?.(a.key, booking)}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
      {footer}
    </div>
  )
}

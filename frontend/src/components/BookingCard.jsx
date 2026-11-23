import { StatusBadge } from './Badges'
import {
  IconCalendar,
  IconChat,
  IconCheckCircle,
  IconCreditCard,
  IconMapPin,
  IconNavigation,
  ServiceCategoryBadge,
} from './Icons'

/** Human label for a booking row. Customer sees "Expert #id", expert sees "Customer #id". */
export default function BookingCard({
  booking,
  perspective = 'customer',
  actions,
  onAction,
  footer,
}) {
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
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <ServiceCategoryBadge serviceName={booking.service_name} size="sm" />
          <div>
            <h3 className="booking-service-title">{booking.service_name}</h3>
            <p className="muted small" style={{ margin: 0 }}>
              Order #{booking.id} ·{' '}
              {perspective === 'expert'
                ? `Customer #${booking.customer_id}`
                : `Expert #${booking.expert_id}`}
            </p>
          </div>
        </div>
        <StatusBadge status={booking.status} />
      </div>

      <div className="card-body">
        <p>
          <IconCalendar size={16} className="muted" />
          <span style={{ fontWeight: 500 }}>{when}</span>
        </p>
        <p>
          <IconMapPin size={16} className="muted" />
          <span className="clamp" title={booking.service_address}>
            {booking.service_address}
          </span>
        </p>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginTop: '8px',
            paddingTop: '8px',
            borderTop: '1px dashed var(--line)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--brand)' }}>
              ₹{Number(booking.service_price).toFixed(2)}
            </span>
            <span className="muted tiny">(Fixed Rate)</span>
          </div>

          {booking.payment_status === 'PAID' ? (
            <span className="paid-tag">
              <IconCheckCircle size={12} /> PAID
            </span>
          ) : (
            <span
              className="badge"
              style={{ background: '#f1f5f9', color: '#64748b', fontSize: '10px' }}
            >
              Payment Pending
            </span>
          )}
        </div>

        {booking.cancellation_reason && (
          <p className="small danger" style={{ marginTop: '8px' }}>
            <strong>Reason:</strong> {booking.cancellation_reason}
          </p>
        )}
        {booking.customer_notes && (
          <p className="small muted" style={{ marginTop: '4px' }}>
            <strong>Notes:</strong> {booking.customer_notes}
          </p>
        )}
      </div>

      {actions?.length > 0 && (
        <div className="card-actions">
          {actions.map((a) => {
            let icon = null
            if (a.key === 'chat') icon = <IconChat size={14} />
            if (a.key === 'track') icon = <IconNavigation size={14} />
            return (
              <button
                key={a.key}
                className={`btn btn-sm ${a.kind || 'btn-primary'}`}
                disabled={a.disabled}
                onClick={() => onAction?.(a.key, booking)}
              >
                {icon}
                <span>{a.label.replace(/^[💬🗺✓✗]+\s*/, '')}</span>
              </button>
            )
          })}
        </div>
      )}
      {footer}
    </div>
  )
}

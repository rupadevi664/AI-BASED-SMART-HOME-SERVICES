import { IconArrowRight, IconCheck, IconShieldCheck, ServiceCategoryBadge } from './Icons'

export default function ServiceCard({ service, onSelect, selected }) {
  return (
    <div className={`card service-card ${selected ? 'selected' : ''}`}>
      <div className="service-card-top">
        <ServiceCategoryBadge serviceName={service.name} size="md" />
        <span className="badge badge-accepted" style={{ fontSize: '10px' }}>
          <IconShieldCheck size={11} />
          <span>Verified</span>
        </span>
      </div>

      <h3 style={{ fontSize: '18px', marginBottom: '6px' }}>{service.name}</h3>
      <p className="muted small clamp" style={{ minHeight: '38px', marginBottom: '14px' }}>
        {service.description}
      </p>

      <div className="price">
        <span className="price-sub">From</span>
        <span>₹{Number(service.base_price).toFixed(0)}</span>
      </div>

      <button
        className={`btn ${selected ? 'btn-secondary' : 'btn-primary'}`}
        onClick={() => onSelect?.(service)}
      >
        {selected ? (
          <>
            <IconCheck size={16} />
            <span>Selected</span>
          </>
        ) : (
          <>
            <span>Find Experts</span>
            <IconArrowRight size={15} />
          </>
        )}
      </button>
    </div>
  )
}

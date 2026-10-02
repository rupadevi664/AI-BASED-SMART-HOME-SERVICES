export default function ServiceCard({ service, onSelect, selected }) {
  return (
    <div className={`card service-card ${selected ? 'selected' : ''}`}>
      <div className="service-icon">🛠️</div>
      <h3>{service.name}</h3>
      <p className="muted small clamp">{service.description}</p>
      <p className="price">₹{Number(service.base_price).toFixed(2)}</p>
      <button className="btn btn-primary" onClick={() => onSelect?.(service)}>
        {selected ? 'Selected ✓' : 'Select'}
      </button>
    </div>
  )
}

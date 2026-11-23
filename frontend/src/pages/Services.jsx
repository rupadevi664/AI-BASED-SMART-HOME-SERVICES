import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { IconSearch, IconSparkles, IconWrench } from '../components/Icons'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import ServiceCard from '../components/ServiceCard'
import { apiError } from '../services/api'
import { listServices } from '../services/serviceService'

export default function Services() {
  const navigate = useNavigate()
  const [services, setServices] = useState(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    listServices()
      .then(setServices)
      .catch((err) => setError(apiError(err)))
  }, [])

  function select(service) {
    navigate('/customer/experts', { state: { service } })
  }

  const filtered = (services || []).filter((s) => {
    if (!query.trim()) return true
    const q = query.toLowerCase()
    return s.name.toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q)
  })

  return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--brand)', fontWeight: 700, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
            <IconSparkles size={14} />
            <span>Guaranteed Quality</span>
          </div>
          <h1 style={{ margin: 0 }}>Service Catalogue</h1>
          <p className="muted" style={{ margin: '4px 0 0' }}>
            Choose from our pre-screened home service offerings with upfront pricing.
          </p>
        </div>

        {/* Search input */}
        <div style={{ position: 'relative', width: '100%', maxWidth: '300px' }}>
          <input
            type="text"
            placeholder="Search services (e.g. AC, plumbing)…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ paddingLeft: '38px', borderRadius: 'var(--radius-full)' }}
          />
          <div style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)', pointerEvents: 'none' }}>
            <IconSearch size={16} />
          </div>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={() => window.location.reload()} />}
      {!services && !error && <Spinner label="Loading service catalogue…" />}

      {services && filtered.length === 0 && (
        <EmptyState
          title="No matching services"
          hint={`We couldn't find any service matching "${query}". Try a different keyword.`}
          icon="🔍"
        >
          <button className="btn btn-outline btn-sm" onClick={() => setQuery('')}>
            Clear Search
          </button>
        </EmptyState>
      )}

      <div className="cards-grid">
        {filtered.map((s) => (
          <ServiceCard key={s.id} service={s} onSelect={select} />
        ))}
      </div>
    </div>
  )
}

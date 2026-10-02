import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ServiceCard from '../components/ServiceCard'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { apiError } from '../services/api'
import { listServices } from '../services/serviceService'

export default function Services() {
  const navigate = useNavigate()
  const [services, setServices] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    listServices()
      .then(setServices)
      .catch((err) => setError(apiError(err)))
  }, [])

  function select(service) {
    navigate('/customer/experts', { state: { service } })
  }

  return (
    <div className="page">
      <h1>Services</h1>
      <p className="muted">Pick a service — we'll find verified experts near you.</p>
      {error && <ErrorState message={error} onRetry={() => window.location.reload()} />}
      {!services && !error && <Spinner />}
      {services && services.length === 0 && (
        <EmptyState title="No services available" hint="The catalogue is empty right now." />
      )}
      <div className="cards-grid">
        {(services || []).map((s) => (
          <ServiceCard key={s.id} service={s} onSelect={select} />
        ))}
      </div>
    </div>
  )
}

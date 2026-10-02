import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ExpertCard from '../components/ExpertCard'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { apiError } from '../services/api'
import useGeolocation from '../hooks/useGeolocation'
import { getNearbyExperts } from '../services/expertService'

export default function NearbyExperts() {
  const location = useLocation()
  const navigate = useNavigate()
  const presetService = location.state?.service || null

  const geo = useGeolocation()
  const [serviceId, setServiceId] = useState(presetService?.id || '')
  const [serviceName, setServiceName] = useState(presetService?.name || '')
  const [radiusKm, setRadiusKm] = useState(10)
  // Manual fallback when GPS is unavailable/denied.
  const [manual, setManual] = useState({ lat: '', lng: '' })
  const [experts, setExperts] = useState(null)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Pre-locate once on mount (browser may prompt for permission).
  useEffect(() => {
    geo.locate().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function search(lat = geo.position?.lat, lng = geo.position?.lng) {
    // Fall back to manually entered coordinates when GPS is missing.
    if ((lat == null || lng == null) && manual.lat !== '' && manual.lng !== '') {
      lat = Number(manual.lat)
      lng = Number(manual.lng)
    }
    if (lat == null || lng == null) {
      setError('We need your location — allow access, or type coordinates below.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const results = await getNearbyExperts({
        latitude: lat,
        longitude: lng,
        radiusKm,
        serviceId: serviceId || undefined,
      })
      setExperts(results)
      setSearched(true)
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  function onViewProfile(expert) {
    navigate('/customer/experts/' + expert.expert_id, {
      state: { expert, serviceId: serviceId || null },
    })
  }
  function onBook(expert) {
    navigate('/customer/book/new', {
      state: {
        expert: {
          expert_id: expert.expert_id,
          name: expert.name,
          services: expert.services,
          location: expert.location,
        },
        serviceId: serviceId || null,
      },
    })
  }

  return (
    <div className="page">
      <h1>Experts near you</h1>
      {presetService && (
        <p className="muted">
          For <strong>{serviceName}</strong> — change it any time.
        </p>
      )}

      <div className="card filter-card">
        <div className="filter-row">
          <div className="filter-item grow">
            <label>Your location</label>
            {geo.position ? (
              <span className="mono small">
                {geo.position.lat.toFixed(5)}, {geo.position.lng.toFixed(5)}
                {geo.position.accuracy ? ` (±${Math.round(geo.position.accuracy)}m)` : ''}
              </span>
            ) : (
              <button className="btn btn-outline btn-sm" onClick={() => geo.locate().catch(() => {})}>
                📍 Get my location
              </button>
            )}
            {geo.error && <p className="danger tiny">{geo.error}</p>}
          </div>
          <div className="filter-item">
            <label>Radius: {radiusKm} km</label>
            <input
              type="range"
              min={1}
              max={50}
              value={radiusKm}
              onChange={(e) => setRadiusKm(Number(e.target.value))}
            />
          </div>
          <div className="filter-item">
            <label>Service</label>
            <select value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
              <option value="">Any service</option>
              {presetService && <option value={presetService.id}>{presetService.name}</option>}
            </select>
          </div>
          <div className="filter-item">
            <label>&nbsp;</label>
            <button className="btn btn-primary" disabled={busy} onClick={() => search()}>
              {busy ? 'Searching…' : 'Search'}
            </button>
          </div>
        </div>
        <details className="manual-coords">
          <summary className="muted tiny">No GPS? Enter coordinates manually</summary>
          <div className="filter-row" style={{ marginTop: 8 }}>
            <div className="filter-item">
              <label>Latitude</label>
              <input
                type="number"
                step="any"
                min={-90}
                max={90}
                placeholder="17.44000"
                value={manual.lat}
                onChange={(e) => setManual({ ...manual, lat: e.target.value })}
              />
            </div>
            <div className="filter-item">
              <label>Longitude</label>
              <input
                type="number"
                step="any"
                min={-180}
                max={180}
                placeholder="78.39000"
                value={manual.lng}
                onChange={(e) => setManual({ ...manual, lng: e.target.value })}
              />
            </div>
          </div>
        </details>
      </div>

      {error && !experts && <ErrorState message={error} onRetry={() => search()} />}
      {busy && <Spinner label="Finding experts…" />}

      {experts && !busy && (
        <>
          <p className="muted small">
            {experts.length} expert{experts.length === 1 ? '' : 's'} within {radiusKm} km
            {serviceId && serviceName ? ` offering ${serviceName}` : ''} — nearest first.
          </p>
          {experts.length === 0 && (
            <EmptyState
              title="No experts found in this radius"
              hint="Try a larger radius, or a different service. Only VERIFIED experts with coordinates appear here."
            />
          )}
          <div className="cards-grid">
            {experts.map((e) => (
              <ExpertCard key={e.expert_id} expert={e} onViewProfile={onViewProfile} onBook={onBook} />
            ))}
          </div>
        </>
      )}

      {!searched && !busy && !error && (
        <EmptyState title="Ready when you are" hint="Allow location access, choose a radius and hit Search." />
      )}
    </div>
  )
}

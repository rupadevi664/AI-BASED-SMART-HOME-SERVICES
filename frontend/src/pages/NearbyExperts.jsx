import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ExpertCard from '../components/ExpertCard'
import {
  IconCrosshair,
  IconFilter,
  IconMapPin,
  IconNavigation,
  IconSearch,
  IconSparkles,
} from '../components/Icons'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import useGeolocation from '../hooks/useGeolocation'
import { apiError } from '../services/api'
import { getNearbyExperts } from '../services/expertService'

export default function NearbyExperts() {
  const location = useLocation()
  const navigate = useNavigate()
  const presetService = location.state?.service || null

  const geo = useGeolocation()
  const [serviceId, setServiceId] = useState(presetService?.id || '')
  const [serviceName, setServiceName] = useState(presetService?.name || '')
  const [radiusKm, setRadiusKm] = useState(10)
  const [manual, setManual] = useState({ lat: '', lng: '' })
  const [experts, setExperts] = useState(null)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Pre-locate once on mount.
  useEffect(() => {
    geo.locate().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function search(lat = geo.position?.lat, lng = geo.position?.lng) {
    if ((lat == null || lng == null) && manual.lat !== '' && manual.lng !== '') {
      lat = Number(manual.lat)
      lng = Number(manual.lng)
    }
    if (lat == null || lng == null) {
      setError('We need your location — click "Get my location" or enter coordinates below.')
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
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ margin: '0 0 4px' }}>Find Verified Experts</h1>
        <p className="muted" style={{ margin: 0 }}>
          {presetService ? (
            <>
              Finding nearby professionals for <strong>{serviceName}</strong>.
            </>
          ) : (
            'Browse nearby service pros sorted by distance.'
          )}
        </p>
      </div>

      <div className="filter-card">
        <div className="filter-row">
          <div className="filter-item grow">
            <label>Your Geolocation</label>
            {geo.position ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'var(--bg-subtle)',
                  padding: '9px 14px',
                  borderRadius: '10px',
                  border: '1.5px solid var(--line)',
                }}
              >
                <IconMapPin size={16} className="brand" />
                <span className="mono small" style={{ fontWeight: 600 }}>
                  {geo.position.lat.toFixed(4)}, {geo.position.lng.toFixed(4)}
                </span>
                {geo.position.accuracy && (
                  <span className="muted tiny">(±{Math.round(geo.position.accuracy)}m)</span>
                )}
              </div>
            ) : (
              <button
                className="btn btn-outline"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => geo.locate().catch(() => {})}
              >
                <IconNavigation size={16} />
                <span>Detect My Location</span>
              </button>
            )}
            {geo.error && <p className="danger tiny" style={{ marginTop: '4px' }}>{geo.error}</p>}
          </div>

          <div className="filter-item" style={{ minWidth: '160px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <label style={{ margin: 0 }}>Radius</label>
              <span className="brand small strong">{radiusKm} km</span>
            </div>
            <input
              type="range"
              min={1}
              max={50}
              value={radiusKm}
              onChange={(e) => setRadiusKm(Number(e.target.value))}
              style={{ cursor: 'pointer', accentColor: 'var(--brand)', marginTop: '8px' }}
            />
          </div>

          <div className="filter-item">
            <label>Service Category</label>
            <select value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
              <option value="">All Services</option>
              {presetService && <option value={presetService.id}>{presetService.name}</option>}
            </select>
          </div>

          <div className="filter-item">
            <label>&nbsp;</label>
            <button className="btn btn-primary" disabled={busy} onClick={() => search()}>
              <IconSearch size={16} />
              <span>{busy ? 'Searching…' : 'Find Nearby'}</span>
            </button>
          </div>
        </div>

        <details className="manual-coords">
          <summary>Can't access GPS? Enter coordinates manually</summary>
          <div className="filter-row" style={{ marginTop: '12px' }}>
            <div className="filter-item">
              <label>Latitude</label>
              <input
                type="number"
                step="any"
                min={-90}
                max={90}
                placeholder="e.g. 17.44000"
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
                placeholder="e.g. 78.39000"
                value={manual.lng}
                onChange={(e) => setManual({ ...manual, lng: e.target.value })}
              />
            </div>
          </div>
        </details>
      </div>

      {error && !experts && <ErrorState message={error} onRetry={() => search()} />}
      {busy && <Spinner label="Scanning nearby verified experts…" />}

      {experts && !busy && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '24px 0 14px' }}>
            <p className="muted small" style={{ margin: 0 }}>
              Found <strong>{experts.length}</strong> verified expert{experts.length === 1 ? '' : 's'} within {radiusKm} km.
            </p>
          </div>
          {experts.length === 0 && (
            <EmptyState
              title="No experts found in this range"
              hint="Try extending your search radius to 25 km or 50 km to find available professionals."
              icon="📍"
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
        <EmptyState
          title="Ready to search"
          hint="Detect your location or type coordinates, set your radius, and click Find Nearby."
          icon="🧭"
        />
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/Loading'
import useGeolocation from '../hooks/useGeolocation'
import { apiError } from '../services/api'
import { createBooking } from '../services/bookingService'
import { getService, listServices } from '../services/serviceService'

/** Time slots every 30 minutes (backend validates the final datetime). */
const SLOTS = []
for (let h = 6; h <= 20; h++) {
  SLOTS.push(`${String(h).padStart(2, '0')}:00:00`, `${String(h).padStart(2, '0')}:30:00`)
}

export default function CreateBooking() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const expert = state?.expert || null
  const geo = useGeolocation()

  const [services, setServices] = useState([])
  const [serviceId, setServiceId] = useState(state?.serviceId ? Number(state.serviceId) : '')
  const [form, setForm] = useState({
    date: '',
    time: '10:00:00',
    address: '',
    notes: '',
  })
  const [useGpsForAddress, setUseGpsForAddress] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listServices().then(setServices).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Preselect the expert's services; if exactly one, lock it in.
  useEffect(() => {
    if (expert?.services?.length === 1 && !serviceId) setServiceId(expert.services[0].id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expert])

  async function attachGps() {
    try {
      const p = await geo.locate()
      setForm((f) => ({ ...f, address: f.address || 'My location (GPS)', notes: f.notes }))
      setUseGpsForAddress(true)
      return p
    } catch {
      return null
    }
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      let lat = null
      let lon = null
      if (useGpsForAddress) {
        const p = geo.position || (await attachGps())
        if (p) {
          lat = p.lat
          lon = p.lng
        }
      }
      await createBooking({
        expert_id: expert.expert_id,
        service_id: Number(serviceId),
        service_address: form.address.trim(),
        service_latitude: lat,
        service_longitude: lon,
        scheduled_date: form.date,
        scheduled_time: form.time,
        customer_notes: form.notes.trim() || null,
      })
      navigate('/customer/bookings', { state: { created: true } })
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  if (!expert) {
    return (
      <div className="page">
        <EmptyState title="No expert selected" hint="Pick an expert from the nearby search first.">
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/customer/experts')}>
            Find experts
          </button>
        </EmptyState>
      </div>
    )
  }

  const expertServiceIds = new Set((expert.services || []).map((s) => s.id))
  const filteredServices = serviceId || !state?.serviceId
    ? services
    : services.filter((s) => expertServiceIds.has(s.id))

  const minDate = new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 10)

  return (
    <div className="page">
      <button className="btn btn-outline btn-sm" onClick={() => navigate(-1)}>← Back</button>
      <h1>Book {expert.name}</h1>

      <form className="card form-card" onSubmit={submit}>
        {error && <div className="alert alert-error">{error}</div>}

        <label>Service</label>
        <select required value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
          <option value="">Choose a service…</option>
          {(filteredServices.length ? filteredServices : services).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — ₹{Number(s.base_price).toFixed(2)}
            </option>
          ))}
        </select>
        <p className="muted tiny">Only experts who offer the chosen service can be booked (server-validated).</p>

        <div className="grid-2">
          <div>
            <label>Date</label>
            <input type="date" required min={minDate} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </div>
          <div>
            <label>Time</label>
            <select required value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })}>
              {SLOTS.map((t) => (
                <option key={t} value={t}>
                  {t.slice(0, 5)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <label>Service address</label>
        <textarea
          required
          minLength={5}
          maxLength={500}
          rows={2}
          value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
          placeholder="Flat 402, Green Meadows, Madhapur, Hyderabad"
        />
        <label className="check-row">
          <input type="checkbox" checked={useGpsForAddress} onChange={(e) => setUseGpsForAddress(e.target.checked)} />
          Attach my GPS coordinates to the booking
        </label>

        <label>Notes for the expert (optional)</label>
        <textarea
          rows={2}
          maxLength={1000}
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          placeholder="Gate code, floor, problem description…"
        />

        <button className="btn btn-primary btn-block" disabled={busy || !serviceId}>
          {busy ? 'Creating booking…' : 'Create booking'}
        </button>
        <p className="muted tiny">
          The booking starts as <strong>PENDING</strong>; the expert accepts or rejects it.
        </p>
      </form>
    </div>
  )
}

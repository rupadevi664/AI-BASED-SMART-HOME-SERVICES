import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  IconAlert,
  IconArrowRight,
  IconCalendar,
  IconClock,
  IconMapPin,
  IconShieldCheck,
  IconUser,
  IconWrench,
} from '../components/Icons'
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
  }, [])

  useEffect(() => {
    if (expert?.services?.length === 1 && !serviceId) setServiceId(expert.services[0].id)
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
        <EmptyState title="No expert selected" hint="Please pick an expert from the nearby directory first.">
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/customer/experts')}>
            Browse Experts
          </button>
        </EmptyState>
      </div>
    )
  }

  const expertServiceIds = new Set((expert.services || []).map((s) => s.id))
  const filteredServices =
    serviceId || !state?.serviceId
      ? services
      : services.filter((s) => expertServiceIds.has(s.id))

  const minDate = new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 10)

  return (
    <div className="page page-narrow">
      <button
        className="btn btn-outline btn-sm"
        onClick={() => navigate(-1)}
        style={{ marginBottom: '16px' }}
      >
        ← Back
      </button>

      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ margin: '0 0 4px' }}>Schedule Appointment</h1>
        <p className="muted" style={{ margin: 0 }}>
          Booking verified professional <strong>{expert.name}</strong>
        </p>
      </div>

      <form className="card form-card" onSubmit={submit}>
        {error && (
          <div className="alert alert-error">
            <IconAlert size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Expert summary chip */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-subtle)',
            padding: '12px 16px',
            borderRadius: '12px',
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div className="expert-avatar" style={{ width: '36px', height: '36px', fontSize: '13px' }}>
              {expert.name ? expert.name.slice(0, 2).toUpperCase() : 'EX'}
            </div>
            <div>
              <strong style={{ display: 'block', fontSize: '15px' }}>{expert.name}</strong>
              <span className="muted tiny">{expert.location}</span>
            </div>
          </div>
          <span className="badge badge-accepted">
            <IconShieldCheck size={12} /> Verified Pro
          </span>
        </div>

        <label>Select Required Service</label>
        <select required value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
          <option value="">Choose a service…</option>
          {(filteredServices.length ? filteredServices : services).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — ₹{Number(s.base_price).toFixed(2)}
            </option>
          ))}
        </select>
        <p className="muted tiny" style={{ margin: '4px 0 12px' }}>
          Upfront locked rate. Payment happens securely after service completion.
        </p>

        <div className="grid-2">
          <div>
            <label>Preferred Date</label>
            <input
              type="date"
              required
              min={minDate}
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
            />
          </div>
          <div>
            <label>Time Window</label>
            <select required value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })}>
              {SLOTS.map((t) => (
                <option key={t} value={t}>
                  {t.slice(0, 5)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <label>Service Address / Landmark</label>
        <textarea
          required
          minLength={5}
          maxLength={500}
          rows={2}
          value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
          placeholder="e.g. Flat 402, Green Meadows, Madhapur, Hyderabad"
        />

        <div style={{ margin: '8px 0 14px' }}>
          <label className="check-row">
            <input
              type="checkbox"
              checked={useGpsForAddress}
              onChange={(e) => setUseGpsForAddress(e.target.checked)}
            />
            <span>Include live GPS pin so the expert can navigate to your door</span>
          </label>
        </div>

        <label>Additional Notes (Optional)</label>
        <textarea
          rows={2}
          maxLength={1000}
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          placeholder="Floor number, gate code, specific symptom or problem details…"
        />

        <button className="btn btn-primary btn-block btn-lg" disabled={busy || !serviceId}>
          {busy ? 'Confirming Appointment…' : 'Confirm & Request Booking'}
          {!busy && <IconArrowRight size={16} />}
        </button>

        <p className="muted tiny center" style={{ marginTop: '12px' }}>
          The expert will receive your booking request instantly. You can chat with them right after acceptance.
        </p>
      </form>
    </div>
  )
}

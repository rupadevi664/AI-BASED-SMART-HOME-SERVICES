import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { VerifyBadge } from '../components/Badges'
import { ErrorState, Spinner } from '../components/Loading'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import { getMyProfile, updateMyProfile } from '../services/expertService'
import { listServices } from '../services/serviceService'

export default function ExpertProfileEditor() {
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [services, setServices] = useState([])
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([getMyProfile(), listServices()])
      .then(([p, s]) => {
        setProfile(p)
        setServices(s)
        setForm({
          skills: p.skills,
          experience_years: p.experience_years,
          location: p.location,
          latitude: p.latitude ?? '',
          longitude: p.longitude ?? '',
          availability: p.availability,
          service_ids: (p.services || []).map((s) => s.id),
        })
      })
      .catch((err) => setError(apiError(err)))
  }, [])

  async function submit(e) {
    e.preventDefault()
    setError('')
    setFlash('')
    setBusy(true)
    try {
      const payload = {
        skills: form.skills.trim(),
        experience_years: Number(form.experience_years),
        location: form.location.trim(),
        availability: form.availability,
        service_ids: form.service_ids,
      }
      if (form.latitude !== '' && form.longitude !== '') {
        payload.latitude = Number(form.latitude)
        payload.longitude = Number(form.longitude)
      }
      await updateMyProfile(payload)
      setFlash('Profile saved.')
      refreshUser()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const toggleService = (id) =>
    setForm((f) => ({
      ...f,
      service_ids: f.service_ids.includes(id)
        ? f.service_ids.filter((x) => x !== id)
        : [...f.service_ids, id],
    }))

  if (error && !profile) return <div className="page"><ErrorState message={error} onRetry={() => window.location.reload()} /></div>
  if (!form) return <div className="page"><Spinner /></div>

  return (
    <div className="page">
      <h1>My expert profile</h1>
      <p className="muted small">
        Profile #{profile.id} · {profile.email} <VerifyBadge status={profile.verification_status} />
      </p>
      {flash && <div className="alert alert-ok">{flash}</div>}
      {error && <ErrorState message={error} />}

      <form className="card form-card" onSubmit={submit}>
        <label>Skills</label>
        <input required minLength={2} maxLength={500} value={form.skills} onChange={set('skills')} />

        <div className="grid-2">
          <div>
            <label>Experience (years)</label>
            <input type="number" min={0} max={60} required value={form.experience_years} onChange={set('experience_years')} />
          </div>
          <div>
            <label>Availability</label>
            <select value={form.availability} onChange={set('availability')}>
              <option value="AVAILABLE">AVAILABLE — bookable</option>
              <option value="UNAVAILABLE">UNAVAILABLE — hidden from booking</option>
            </select>
          </div>
        </div>

        <label>Base location</label>
        <input required minLength={2} maxLength={255} value={form.location} onChange={set('location')} />

        <div className="grid-2">
          <div>
            <label>Latitude (for nearby search)</label>
            <input type="number" step="any" min={-90} max={90} value={form.latitude} onChange={set('latitude')} />
          </div>
          <div>
            <label>Longitude</label>
            <input type="number" step="any" min={-180} max={180} value={form.longitude} onChange={set('longitude')} />
          </div>
        </div>
        <p className="muted tiny">Static profile coordinates used by the Haversine nearby search — not live GPS.</p>

        <label>Services you offer</label>
        <div className="chip-select">
          {services.map((s) => (
            <button
              type="button"
              key={s.id}
              className={`chip-tag ${form.service_ids.includes(s.id) ? 'on' : ''}`}
              onClick={() => toggleService(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>

        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Saving…' : 'Save profile'}
        </button>
      </form>
    </div>
  )
}

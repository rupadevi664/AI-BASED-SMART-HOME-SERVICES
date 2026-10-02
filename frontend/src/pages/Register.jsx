import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import {
  getMe,
  login as loginApi,
  registerCustomer,
  registerExpert,
} from '../services/authService'
import { listServices } from '../services/serviceService'
import { useEffect } from 'react'

const ROLE_HOME = {
  ADMIN: '/admin/dashboard',
  EXPERT: '/expert/dashboard',
  CUSTOMER: '/customer/dashboard',
}

export default function Register() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState('customer')
  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    password: '',
    skills: '',
    experience_years: 1,
    location: '',
    latitude: '',
    longitude: '',
  })
  const [serviceIds, setServiceIds] = useState([])
  const [services, setServices] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listServices().then(setServices).catch(() => setServices([]))
  }, [])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      let accessToken, me
      if (mode === 'customer') {
        await registerCustomer({
          name: form.name.trim(),
          email: form.email.trim(),
          phone: form.phone.trim(),
          password: form.password,
        })
        ;({ access_token: accessToken } = await loginApi(form.email.trim(), form.password))
        me = await getMe(accessToken)
      } else {
        // ExpertRegister schema: coords/service links optional.
        const payload = {
          name: form.name.trim(),
          email: form.email.trim(),
          phone: form.phone.trim(),
          password: form.password,
          skills: form.skills.trim(),
          experience_years: Number(form.experience_years) || 0,
          location: form.location.trim(),
          availability: 'AVAILABLE',
          service_ids: serviceIds.length ? serviceIds.map(Number) : null,
        }
        if (form.latitude !== '' && form.longitude !== '') {
          payload.latitude = Number(form.latitude)
          payload.longitude = Number(form.longitude)
        }
        await registerExpert(payload)
        ;({ access_token: accessToken } = await loginApi(form.email.trim(), form.password))
        me = await getMe(accessToken)
      }
      login(accessToken, me)
      navigate(ROLE_HOME[me.role] || '/', { replace: true })
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="card auth-card auth-card-wide" onSubmit={submit}>
        <h2>Create your account</h2>
        <div className="mode-switch">
          <button type="button" className={`btn btn-sm ${mode === 'customer' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setMode('customer')}>
            I'm a Customer
          </button>
          <button type="button" className={`btn btn-sm ${mode === 'expert' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setMode('expert')}>
            I'm an Expert
          </button>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <label>Full name</label>
        <input required minLength={2} value={form.name} onChange={set('name')} placeholder="Rupa Devi" />

        <div className="grid-2">
          <div>
            <label>Email</label>
            <input type="email" required value={form.email} onChange={set('email')} placeholder="you@example.com" />
          </div>
          <div>
            <label>Phone</label>
            <input required minLength={7} maxLength={20} value={form.phone} onChange={set('phone')} placeholder="9999999999" />
          </div>
        </div>

        <label>Password</label>
        <input type="password" required minLength={8} value={form.password} onChange={set('password')} placeholder="min 8 characters" autoComplete="new-password" />

        {mode === 'expert' && (
          <>
            <hr className="sep" />
            <label>Skills</label>
            <input required minLength={2} value={form.skills} onChange={set('skills')} placeholder="wiring, fans, inverters" />
            <div className="grid-2">
              <div>
                <label>Experience (years)</label>
                <input type="number" min={0} max={60} required value={form.experience_years} onChange={set('experience_years')} />
              </div>
              <div>
                <label>Base location</label>
                <input required minLength={2} value={form.location} onChange={set('location')} placeholder="Indiranagar, Bengaluru" />
              </div>
            </div>
            <div className="grid-2">
              <div>
                <label>Latitude (optional)</label>
                <input type="number" step="any" min={-90} max={90} value={form.latitude} onChange={set('latitude')} placeholder="17.44" />
              </div>
              <div>
                <label>Longitude (optional)</label>
                <input type="number" step="any" min={-180} max={180} value={form.longitude} onChange={set('longitude')} placeholder="78.39" />
              </div>
            </div>

            <label>Services you offer (optional)</label>
            <div className="chip-select">
              {services.map((s) => (
                <button
                  type="button"
                  key={s.id}
                  className={`chip-tag ${serviceIds.includes(s.id) ? 'on' : ''}`}
                  onClick={() =>
                    setServiceIds((ids) => (ids.includes(s.id) ? ids.filter((x) => x !== s.id) : [...ids, s.id]))
                  }
                >
                  {s.name}
                </button>
              ))}
            </div>
          </>
        )}

        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Creating account…' : mode === 'customer' ? 'Create customer account' : 'Create expert account'}
        </button>
        <p className="muted small center">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  )
}

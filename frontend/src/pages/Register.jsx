import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { IconAlert, IconArrowRight, IconBriefcase, IconHome, IconUser } from '../components/Icons'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import {
  getMe,
  login as loginApi,
  registerCustomer,
  registerExpert,
} from '../services/authService'
import { listServices } from '../services/serviceService'

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
      <form className="auth-card auth-card-wide" onSubmit={submit}>
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              background: 'var(--brand-gradient)',
              borderRadius: '14px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              marginBottom: '10px',
              boxShadow: 'var(--shadow-primary)',
            }}
          >
            <IconHome size={24} />
          </div>
          <h2 style={{ fontSize: '24px', margin: '0 0 4px' }}>Create an Account</h2>
          <p className="muted small" style={{ margin: 0 }}>
            Join thousands of satisfied homeowners and verified service providers.
          </p>
        </div>

        {/* Mode Selector */}
        <div className="mode-switch">
          <button
            type="button"
            className={mode === 'customer' ? 'active' : ''}
            onClick={() => setMode('customer')}
          >
            <IconUser size={14} />
            <span>I'm a Customer</span>
          </button>
          <button
            type="button"
            className={mode === 'expert' ? 'active' : ''}
            onClick={() => setMode('expert')}
          >
            <IconBriefcase size={14} />
            <span>I'm a Service Expert</span>
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            <IconAlert size={16} />
            <span>{error}</span>
          </div>
        )}

        <label>Full Name</label>
        <input required minLength={2} value={form.name} onChange={set('name')} placeholder="e.g. Rupa Devi" />

        <div className="grid-2">
          <div>
            <label>Email Address</label>
            <input type="email" required value={form.email} onChange={set('email')} placeholder="you@example.com" />
          </div>
          <div>
            <label>Phone Number</label>
            <input required minLength={7} maxLength={20} value={form.phone} onChange={set('phone')} placeholder="+91 98765 43210" />
          </div>
        </div>

        <label>Create Password</label>
        <input
          type="password"
          required
          minLength={8}
          value={form.password}
          onChange={set('password')}
          placeholder="Minimum 8 characters"
          autoComplete="new-password"
        />

        {mode === 'expert' && (
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px dashed var(--line)' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--brand)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Expert Professional Details
            </span>

            <label>Skills & Specialization</label>
            <input required minLength={2} value={form.skills} onChange={set('skills')} placeholder="e.g. Residential wiring, AC servicing, plumbing fixtures" />

            <div className="grid-2">
              <div>
                <label>Experience (Years)</label>
                <input type="number" min={0} max={60} required value={form.experience_years} onChange={set('experience_years')} />
              </div>
              <div>
                <label>Base Operating City / Area</label>
                <input required minLength={2} value={form.location} onChange={set('location')} placeholder="e.g. Indiranagar, Bengaluru" />
              </div>
            </div>

            <div className="grid-2">
              <div>
                <label>Base Latitude (Optional)</label>
                <input type="number" step="any" min={-90} max={90} value={form.latitude} onChange={set('latitude')} placeholder="e.g. 17.44" />
              </div>
              <div>
                <label>Base Longitude (Optional)</label>
                <input type="number" step="any" min={-180} max={180} value={form.longitude} onChange={set('longitude')} placeholder="e.g. 78.39" />
              </div>
            </div>

            <label>Services You Provide</label>
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
          </div>
        )}

        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
          {busy ? 'Registering…' : mode === 'customer' ? 'Create Customer Account' : 'Register as Expert'}
          {!busy && <IconArrowRight size={16} />}
        </button>

        <p className="muted small center" style={{ marginTop: '20px' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ fontWeight: 600 }}>
            Sign in
          </Link>
        </p>
      </form>
    </div>
  )
}

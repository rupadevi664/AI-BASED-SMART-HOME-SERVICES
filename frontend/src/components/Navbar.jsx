import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import NotificationBell from './NotificationBell'
import {
  IconBot,
  IconBriefcase,
  IconCalendar,
  IconHome,
  IconLogOut,
  IconUser,
  IconWrench,
} from './Icons'

const LINKS = {
  CUSTOMER: [
    { to: '/customer/dashboard', label: 'Dashboard', icon: IconHome },
    { to: '/customer/services', label: 'Services', icon: IconWrench },
    { to: '/customer/bookings', label: 'My Bookings', icon: IconCalendar },
    { to: '/customer/assistant', label: 'AI Copilot', icon: IconBot },
  ],
  EXPERT: [
    { to: '/expert/dashboard', label: 'Dashboard', icon: IconHome },
    { to: '/expert/bookings', label: 'Booking Requests', icon: IconCalendar },
    { to: '/expert/profile', label: 'My Profile', icon: IconBriefcase },
  ],
  ADMIN: [
    { to: '/admin/dashboard', label: 'Dashboard', icon: IconHome },
  ],
}

export default function Navbar() {
  const { user, role, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const links = LINKS[role] || []

  function handleLogout() {
    logout()
    navigate('/login')
  }

  // Initials for avatar
  const initials = user?.name
    ? user.name
        .split(' ')
        .map((p) => p[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'U'

  const homePath =
    role === 'ADMIN'
      ? '/admin/dashboard'
      : role === 'EXPERT'
        ? '/expert/dashboard'
        : '/customer/dashboard'

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to={homePath} className="brand">
          <div className="brand-icon">
            <IconHome size={20} />
          </div>
          <span>SmartHome</span>
          <span className="brand-badge">AI</span>
        </Link>

        <button
          className="nav-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle navigation menu"
        >
          {open ? '✕' : '☰'}
        </button>

        <nav className={`nav-links ${open ? 'open' : ''}`}>
          {links.map((l) => {
            const IconComp = l.icon
            return (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) => (isActive ? 'active' : '')}
                onClick={() => setOpen(false)}
              >
                {IconComp && <IconComp size={16} />}
                <span>{l.label}</span>
              </NavLink>
            )
          })}

          <span className="nav-spacer" />

          {user && <NotificationBell />}

          {user && (
            <div className="nav-user" title={user.email}>
              <div className="user-avatar">{initials}</div>
              <span>{user.name}</span>
              <span className="role-chip">{role}</span>
            </div>
          )}

          {user ? (
            <button
              className="btn btn-outline btn-sm"
              onClick={handleLogout}
              style={{ background: 'rgba(255,255,255,0.06)', color: '#fff', borderColor: 'rgba(255,255,255,0.15)' }}
            >
              <IconLogOut size={14} />
              <span>Logout</span>
            </button>
          ) : (
            <Link to="/login" className="btn btn-primary btn-sm">
              Sign In
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}

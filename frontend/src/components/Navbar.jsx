import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const LINKS = {
  CUSTOMER: [
    { to: '/customer/dashboard', label: 'Dashboard' },
    { to: '/customer/services', label: 'Services' },
    { to: '/customer/bookings', label: 'My Bookings' },
    { to: '/customer/assistant', label: 'AI Assistant' },
  ],
  EXPERT: [
    { to: '/expert/dashboard', label: 'Dashboard' },
    { to: '/expert/bookings', label: 'Booking Requests' },
    { to: '/expert/profile', label: 'My Profile' },
  ],
  ADMIN: [
    { to: '/admin/dashboard', label: 'Dashboard' },
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

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to={role === 'ADMIN' ? '/admin/dashboard' : role === 'EXPERT' ? '/expert/dashboard' : '/customer/dashboard'} className="brand">
          🏠 SmartHome
        </Link>
        <button className="nav-toggle" onClick={() => setOpen((v) => !v)} aria-label="Toggle menu">
          ☰
        </button>
        <nav className={`nav-links ${open ? 'open' : ''}`}>
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} className={({ isActive }) => (isActive ? 'active' : '')} onClick={() => setOpen(false)}>
              {l.label}
            </NavLink>
          ))}
          <span className="nav-spacer" />
          {user && (
            <span className="nav-user" title={user.email}>
              {user.name} <span className="role-chip">{role}</span>
            </span>
          )}
          <button className="btn btn-outline btn-sm" onClick={handleLogout}>
            Logout
          </button>
        </nav>
      </div>
    </header>
  )
}

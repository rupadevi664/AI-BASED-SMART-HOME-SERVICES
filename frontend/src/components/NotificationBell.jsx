import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  deleteNotification,
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
} from '../services/notificationService'
import {
  IconBell,
  IconCalendar,
  IconCheck,
  IconCheckCircle,
  IconCreditCard,
  IconShieldCheck,
  IconSparkles,
  IconStar,
  IconWrench,
  IconX,
} from './Icons'

function formatRelativeTime(dateStr) {
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const diffSec = Math.floor((now - d) / 1000)
    if (diffSec < 45) return 'Just now'
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`
    return d.toLocaleDateString()
  } catch {
    return ''
  }
}

function getNotificationVisual(type) {
  switch (type) {
    case 'BOOKING_CREATED':
      return { icon: <IconCalendar size={15} />, bg: '#eff6ff', color: '#2563eb' }
    case 'BOOKING_ACCEPTED':
      return { icon: <IconCheckCircle size={15} />, bg: '#ecfdf5', color: '#16a34a' }
    case 'BOOKING_REJECTED':
    case 'BOOKING_CANCELLED':
      return { icon: <IconX size={15} />, bg: '#fef2f2', color: '#dc2626' }
    case 'BOOKING_COMPLETED':
      return { icon: <IconCheck size={15} />, bg: '#f3e8ff', color: '#9333ea' }
    case 'PAYMENT_SUCCESS':
      return { icon: <IconCreditCard size={15} />, bg: '#ecfdf5', color: '#059669' }
    case 'REVIEW_ADDED':
      return { icon: <IconStar size={15} />, bg: '#fffbeb', color: '#d97706' }
    case 'VERIFICATION_UPDATE':
      return { icon: <IconShieldCheck size={15} />, bg: '#e0f2fe', color: '#0284c7' }
    default:
      return { icon: <IconSparkles size={15} />, bg: '#f1f5f9', color: '#475569' }
  }
}

export default function NotificationBell() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const menuRef = useRef(null)

  // Fetch unread count periodically
  useEffect(() => {
    if (!user) return
    let active = true

    async function checkCount() {
      try {
        const count = await getUnreadCount()
        if (active) setUnreadCount(count)
      } catch {
        // silent fallback
      }
    }

    checkCount()
    const timer = setInterval(checkCount, 15000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [user])

  // Load full list when menu opened
  async function loadList() {
    setLoading(true)
    try {
      const data = await getNotifications(false, 30)
      setNotifications(data)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  function toggleOpen() {
    if (!open) {
      loadList()
    }
    setOpen((v) => !v)
  }

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  async function handleNotificationClick(n) {
    if (!n.is_read) {
      try {
        await markAsRead(n.id)
        setNotifications((list) =>
          list.map((item) => (item.id === n.id ? { ...item, is_read: true } : item)),
        )
        setUnreadCount((c) => Math.max(0, c - 1))
      } catch {
        // proceed anyway
      }
    }
    if (n.link) {
      setOpen(false)
      navigate(n.link)
    }
  }

  async function handleMarkAllRead() {
    try {
      await markAllAsRead()
      setNotifications((list) => list.map((item) => ({ ...item, is_read: true })))
      setUnreadCount(0)
    } catch {
      // silent
    }
  }

  async function handleDelete(e, id) {
    e.stopPropagation()
    try {
      await deleteNotification(id)
      setNotifications((list) => list.filter((item) => item.id !== id))
      setUnreadCount((c) => Math.max(0, c - 1))
    } catch {
      // silent
    }
  }

  if (!user) return null

  return (
    <div className="notif-wrapper" ref={menuRef}>
      <button
        type="button"
        className="notif-bell-btn"
        onClick={toggleOpen}
        aria-label="View notifications"
        title="Notifications"
      >
        <IconBell size={18} />
        {unreadCount > 0 && (
          <span className="notif-badge">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <strong>Notifications</strong>
              {unreadCount > 0 && (
                <span className="badge badge-accepted" style={{ fontSize: '10px' }}>
                  {unreadCount} new
                </span>
              )}
            </div>
            {notifications.some((n) => !n.is_read) && (
              <button
                type="button"
                className="notif-action-btn"
                onClick={handleMarkAllRead}
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="notif-body">
            {loading && notifications.length === 0 && (
              <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--muted)', fontSize: '13px' }}>
                Loading updates…
              </div>
            )}

            {!loading && notifications.length === 0 && (
              <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--muted)' }}>
                <span style={{ fontSize: '28px', display: 'block', marginBottom: '6px' }}>🔔</span>
                <strong style={{ display: 'block', color: 'var(--ink)', fontSize: '14px', marginBottom: '2px' }}>
                  No notifications yet
                </strong>
                <span className="small">We'll alert you here when your service or booking status updates.</span>
              </div>
            )}

            {notifications.map((n) => {
              const visual = getNotificationVisual(n.type)
              return (
                <div
                  key={n.id}
                  className={`notif-item ${!n.is_read ? 'unread' : ''}`}
                  onClick={() => handleNotificationClick(n)}
                >
                  <div
                    className="notif-item-icon"
                    style={{ background: visual.bg, color: visual.color }}
                  >
                    {visual.icon}
                  </div>

                  <div className="notif-item-content">
                    <div className="notif-item-title">
                      <span>{n.title}</span>
                      {!n.is_read && <span className="notif-dot" />}
                    </div>
                    <div className="notif-item-message">{n.message}</div>
                    <div className="notif-item-time">{formatRelativeTime(n.created_at)}</div>
                  </div>

                  <button
                    type="button"
                    className="notif-del-btn"
                    title="Dismiss"
                    onClick={(e) => handleDelete(e, n.id)}
                  >
                    <IconX size={13} />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { getMe } from '../services/authService'
import { TOKEN_KEY, USER_KEY } from '../services/authService'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY)) || null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(Boolean(localStorage.getItem(TOKEN_KEY)))

  // On boot with a stored token, re-validate it against GET /auth/me.
  // Also re-fetches whenever the identity changes so /me stays fresh.
  useEffect(() => {
    let cancelled = false
    if (!token) {
      setLoading(false)
      return
    }
    setLoading(true)
    getMe()
      .then((me) => {
        if (!cancelled) {
          setUser(me)
          localStorage.setItem(USER_KEY, JSON.stringify(me))
        }
      })
      .catch(() => {
        if (!cancelled) {
          // Invalid/expired token: interceptor usually clears it first.
          localStorage.removeItem(TOKEN_KEY)
          localStorage.removeItem(USER_KEY)
          setToken(null)
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  const login = useCallback((accessToken, me) => {
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY, JSON.stringify(me))
    setToken(accessToken)
    setUser(me)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      isAuthenticated: Boolean(token && user),
      role: user?.role || null,
      isCustomer: user?.role === 'CUSTOMER',
      isExpert: user?.role === 'EXPERT',
      isAdmin: user?.role === 'ADMIN',
      expertProfile: user?.expert_profile || null,
      login,
      logout,
      refreshUser: () => setToken((t) => t), // re-triggers the /me effect
    }),
    [token, user, loading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

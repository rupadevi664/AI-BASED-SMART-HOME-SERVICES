import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Spinner } from '../components/Loading'

/** Blocks access unless authenticated (optional allowedRoles check). */
export default function ProtectedRoute({ allowedRoles, children }) {
  const { isAuthenticated, loading, role } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="page-center">
        <Spinner />
      </div>
    )
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  if (allowedRoles && !allowedRoles.includes(role)) {
    // Signed in, wrong role: send them to their own dashboard.
    const home =
      role === 'ADMIN' ? '/admin/dashboard' : role === 'EXPERT' ? '/expert/dashboard' : '/customer/dashboard'
    return <Navigate to={home} replace />
  }
  return children
}

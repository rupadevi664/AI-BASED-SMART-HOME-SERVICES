import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import { AuthProvider } from './context/AuthContext'
import AdminDashboard from './pages/AdminDashboard'
import AIAssistant from './pages/AIAssistant'
import Chat from './pages/Chat'
import CreateBooking from './pages/CreateBooking'
import CustomerDashboard from './pages/CustomerDashboard'
import ExpertBookings from './pages/ExpertBookings'
import ExpertDashboard from './pages/ExpertDashboard'
import ExpertProfile from './pages/ExpertProfile'
import ExpertProfileEditor from './pages/ExpertProfileEditor'
import LiveTracking from './pages/LiveTracking'
import Login from './pages/Login'
import MyBookings from './pages/MyBookings'
import NearbyExperts from './pages/NearbyExperts'
import Register from './pages/Register'
import Services from './pages/Services'
import ProtectedRoute from './routes/AppRoutes'

const CUSTOMER = ['CUSTOMER']
const EXPERT = ['EXPERT']
const ADMIN = ['ADMIN']

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="app-shell">
          <Navbar />
          <main className="main-area">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

              <Route path="/customer/dashboard" element={<ProtectedRoute allowedRoles={CUSTOMER}><CustomerDashboard /></ProtectedRoute>} />
              <Route path="/customer/services" element={<ProtectedRoute allowedRoles={CUSTOMER}><Services /></ProtectedRoute>} />
              <Route path="/customer/experts" element={<ProtectedRoute allowedRoles={CUSTOMER}><NearbyExperts /></ProtectedRoute>} />
              <Route path="/customer/experts/:id" element={<ProtectedRoute allowedRoles={CUSTOMER}><ExpertProfile /></ProtectedRoute>} />
              <Route path="/customer/book/new" element={<ProtectedRoute allowedRoles={CUSTOMER}><CreateBooking /></ProtectedRoute>} />
              <Route path="/customer/bookings" element={<ProtectedRoute allowedRoles={CUSTOMER}><MyBookings /></ProtectedRoute>} />
              <Route path="/customer/bookings/:bookingId/chat" element={<ProtectedRoute allowedRoles={CUSTOMER}><Chat /></ProtectedRoute>} />
              <Route path="/customer/bookings/:bookingId/tracking" element={<ProtectedRoute allowedRoles={CUSTOMER}><LiveTracking /></ProtectedRoute>} />
              <Route path="/customer/assistant" element={<ProtectedRoute allowedRoles={CUSTOMER}><AIAssistant /></ProtectedRoute>} />

              <Route path="/expert/dashboard" element={<ProtectedRoute allowedRoles={EXPERT}><ExpertDashboard /></ProtectedRoute>} />
              <Route path="/expert/bookings" element={<ProtectedRoute allowedRoles={EXPERT}><ExpertBookings /></ProtectedRoute>} />
              <Route path="/expert/profile" element={<ProtectedRoute allowedRoles={EXPERT}><ExpertProfileEditor /></ProtectedRoute>} />
              <Route path="/expert/bookings/:bookingId/chat" element={<ProtectedRoute allowedRoles={EXPERT}><Chat /></ProtectedRoute>} />
              <Route path="/expert/bookings/:bookingId/tracking" element={<ProtectedRoute allowedRoles={EXPERT}><LiveTracking /></ProtectedRoute>} />

              <Route path="/admin/dashboard" element={<ProtectedRoute allowedRoles={ADMIN}><AdminDashboard /></ProtectedRoute>} />

              <Route path="*" element={<Login />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </AuthProvider>
  )
}

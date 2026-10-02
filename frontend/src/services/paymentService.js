import { api } from './api'

// --- Phase 6: Razorpay payments (backend verifies every signature) ---------
// The Razorpay KEY_SECRET never touches the frontend; the backend returns
// key_id + order details in the create-order response.

// POST /payments/create-order/{booking_id} → Checkout payload
export async function createPaymentOrder(bookingId) {
  const { data } = await api.post(`/payments/create-order/${bookingId}`)
  return data
}

// POST /payments/verify — backend checks the HMAC signature server-side.
// Body: { razorpay_order_id, razorpay_payment_id, razorpay_signature }
export async function verifyPayment(payload) {
  const { data } = await api.post('/payments/verify', payload)
  return data
}

// GET /payments/my-payments — customer payment history
export async function getMyPayments() {
  const { data } = await api.get('/payments/my-payments')
  return data
}

// GET /payments/booking/{booking_id} — attempts for one booking
export async function getPaymentsForBooking(bookingId) {
  const { data } = await api.get(`/payments/booking/${bookingId}`)
  return data
}

// Load the Razorpay Checkout script once (https://checkout.razorpay.com/v1/checkout.js).
export function loadRazorpayScript() {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve(true)
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve(true)
    script.onerror = () => reject(new Error('Failed to load Razorpay Checkout. Check your internet connection.'))
    document.body.appendChild(script)
  })
}

/**
 * Open Razorpay Checkout and resolve the handler payload
 * { razorpay_order_id, razorpay_payment_id, razorpay_signature } on success.
 * Rejects when the modal is dismissed or checkout cannot open.
 */
export function openRazorpayCheckout(order, options = {}) {
  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay({
      key: order.key_id,
      amount: Math.round(order.amount * 100), // paise
      currency: order.currency,
      name: 'AI Smart Home Services',
      description: `${order.service_name} · Booking #${order.booking_id}`,
      order_id: order.razorpay_order_id,
      prefill: {
        name: order.customer_name,
        email: order.customer_email,
        contact: order.prefill_contact || '',
      },
      theme: { color: '#2563eb' },
      modal: {
        ondismiss: () => reject(new Error('Payment cancelled')),
      },
      handler: (response) => resolve(response),
      ...options,
    })
    rzp.on('payment.failed', (resp) => reject(new Error(resp?.error?.description || 'Payment failed at Razorpay')))
    rzp.open()
  })
}

import { useState } from 'react'
import { apiError } from '../services/api'
import { createPaymentOrder, loadRazorpayScript, openRazorpayCheckout, verifyPayment } from '../services/paymentService'

/**
 * Pay Now (Phase 6). Creates a Razorpay order, opens Checkout, and — only
 * after the backend verifies the signature — shows the success receipt.
 */
export default function PayNow({ booking }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)

  async function pay() {
    setBusy(true)
    setError('')
    setReceipt(null)
    try {
      await loadRazorpayScript()
      const order = await createPaymentOrder(booking.id)
      try {
        const checkout = await openRazorpayCheckout(order)
        const verified = await verifyPayment(checkout)
        setReceipt({
          paymentId: verified.razorpay_payment_id,
          bookingId: verified.booking_id,
          amount: verified.amount,
          status: verified.status,
        })
      } catch (checkoutErr) {
        // Dismissed modal or payment.failed — distinguishable, both non-paid.
        setError(checkoutErr.message || 'Payment did not complete.')
      }
    } catch (err) {
      setError(apiError(err) || err.message)
    } finally {
      setBusy(false)
    }
  }

  if (receipt) {
    return (
      <div className="pay-success">
        <p className="strong">✅ Payment successful</p>
        <p className="small">Payment ID: {receipt.paymentId}</p>
        <p className="small">Booking #{receipt.bookingId} · ₹{Number(receipt.amount).toFixed(2)}</p>
      </div>
    )
  }

  const alreadyPaid = booking.payment_status === 'PAID'

  return (
    <div className="pay-now">
      <button className="btn btn-primary btn-sm" disabled={busy || alreadyPaid} onClick={pay}>
        {busy ? 'Opening checkout…' : alreadyPaid ? 'Paid' : `Pay ₹${Number(booking.service_price).toFixed(2)}`}
      </button>
      {error && <p className="small danger">{error}</p>}
    </div>
  )
}

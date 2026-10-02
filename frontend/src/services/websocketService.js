import { chatSocketUrl, locationSocketUrl } from './bookingService'

/**
 * Minimal JSON-over-WebSocket client for the backend's booking sockets.
 * The server sends: connected/user_joined/user_left/message/pong/location_update/error.
 * Reconnects with capped backoff (chat + location sockets tolerate it).
 */
export class BookingSocket {
  constructor({ bookingId, token, channel = 'chat', onEvent, onStatus }) {
    this.bookingId = bookingId
    this.token = token
    this.channel = channel // 'chat' | 'location'
    this.onEvent = onEvent
    this.onStatus = onStatus
    this.ws = null
    this.attempt = 0
    this.stopped = false
    this.pingTimer = null
  }

  url() {
    return this.channel === 'location'
      ? locationSocketUrl(this.bookingId, this.token)
      : chatSocketUrl(this.bookingId, this.token)
  }

  connect() {
    if (this.stopped) return
    this.onStatus?.('connecting')
    try {
      this.ws = new WebSocket(this.url())
    } catch {
      this.onStatus?.('error')
      this.scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this.attempt = 0
      this.onStatus?.('connected')
      // Application-level keepalive (server answers {"type":"pong"}).
      this.pingTimer = setInterval(() => this.send({ type: 'ping' }), 25000)
    }

    this.ws.onmessage = (e) => {
      try {
        this.onEvent?.(JSON.parse(e.data))
      } catch {
        this.onEvent?.({ type: 'error', message: 'Unparseable server frame' })
      }
    }

    this.ws.onclose = (e) => {
      clearInterval(this.pingTimer)
      this.onStatus?.('closed')
      // Retry indefinitely (capped backoff): a backend restart or brief
      // network drop should recover automatically. Call stop() to end.
      if (!this.stopped) this.scheduleReconnect()
    }

    this.ws.onerror = () => this.onStatus?.('error')
  }

  scheduleReconnect() {
    this.attempt += 1
    const delay = Math.min(1000 * 2 ** (this.attempt - 1), 8000)
    setTimeout(() => {
      if (!this.stopped) this.connect()
    }, delay)
  }

  send(obj) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj))
  }

  stop() {
    this.stopped = true
    clearInterval(this.pingTimer)
    this.ws?.close()
  }
}

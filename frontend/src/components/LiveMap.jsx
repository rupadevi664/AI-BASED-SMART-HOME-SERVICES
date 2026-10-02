import { useEffect, useRef, useState } from 'react'

/** Reusable Leaflet map. Markers update in place; map re-centers when the expert moves. */
export default function LiveMap({ customerPos, expertPos, height = 420 }) {
  const mapRef = useRef(null)
  const containerRef = useRef(null)
  const customerMarkerRef = useRef(null)
  const expertMarkerRef = useRef(null)
  const centeredRef = useRef(false)
  const [ready, setReady] = useState(false)

  // Init once.
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return
    let map
    import('leaflet').then((L) => {
      map = L.map(containerRef.current, { zoomControl: true }).setView([17.385, 78.4867], 13)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(map)
      mapRef.current = { map, L }
      setReady(true)
    })
    return () => {
      map?.remove()
      mapRef.current = null
    }
  }, [])

  // Customer marker (home).
  useEffect(() => {
    const ctx = mapRef.current
    if (!ctx || !customerPos) return
    const { map, L } = ctx
    const ll = [customerPos.lat, customerPos.lng]
    if (!customerMarkerRef.current) {
      customerMarkerRef.current = L.marker(ll, {
        icon: L.divIcon({ className: 'cust-pin', html: '🏠', iconSize: [28, 28], iconAnchor: [14, 14] }),
      }).addTo(map)
    } else {
      customerMarkerRef.current.setLatLng(ll)
    }
    fitBoth()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerPos?.lat, customerPos?.lng, ready])

  // Expert marker (moving).
  useEffect(() => {
    const ctx = mapRef.current
    if (!ctx || !expertPos) return
    const { map, L } = ctx
    const ll = [expertPos.lat, expertPos.lng]
    if (!expertMarkerRef.current) {
      expertMarkerRef.current = L.marker(ll, {
        icon: L.divIcon({ className: 'exp-pin', html: '🛠️', iconSize: [28, 28], iconAnchor: [14, 14] }),
      }).addTo(map)
    } else {
      expertMarkerRef.current.setLatLng(ll)
    }
    // Recentre once when the expert first appears, then follow silently.
    if (!centeredRef.current) {
      centeredRef.current = true
      map.setView(ll, Math.max(map.getZoom(), 14))
    }
    fitBoth()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expertPos?.lat, expertPos?.lng, ready])

  function fitBoth() {
    const ctx = mapRef.current
    if (!ctx) return
    const { map, L } = ctx
    const pts = []
    if (customerMarkerRef.current) pts.push(customerMarkerRef.current.getLatLng())
    if (expertMarkerRef.current) pts.push(expertMarkerRef.current.getLatLng())
    if (pts.length === 2) {
      map.fitBounds(L.latLngBounds(pts).pad(0.35))
    }
  }

  return (
    <div className="map-shell">
      <div ref={containerRef} style={{ height, width: '100%' }} className="map-container" />
      {!customerPos && !expertPos && (
        <div className="map-overlay muted">Waiting for location data…</div>
      )}
    </div>
  )
}

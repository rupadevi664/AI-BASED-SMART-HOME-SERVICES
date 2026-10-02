import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Browser Geolocation API wrapper.
 * - `locate()` — one-shot getCurrentPosition
 * - start/stop `watch()` — watchPosition streaming (expert location sharing)
 */
export default function useGeolocation() {
  const [position, setPosition] = useState(null)
  const [error, setError] = useState('')
  const [watching, setWatching] = useState(false)
  const watchIdRef = useRef(null)

  const locate = useCallback(() => {
    return new Promise((resolve, reject) => {
      if (!('geolocation' in navigator)) {
        setError('Geolocation is not supported by this browser.')
        reject(new Error('unsupported'))
        return
      }

      // Fallback for laptops/desktops without hardware GPS
      const fallbackLowAccuracy = () => {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const p = { lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy }
            setPosition(p)
            setError('')
            resolve(p)
          },
          (err) => {
            const msg =
              err.code === 1
                ? 'Location permission denied — allow it in your browser to continue.'
                : err.code === 3
                  ? 'Location request timed out. Please check Windows Location Services or enter coordinates manually.'
                  : 'Location unavailable right now.'
            setError(msg)
            reject(new Error(msg))
          },
          { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 },
        )
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const p = { lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy }
          setPosition(p)
          setError('')
          resolve(p)
        },
        (err) => {
          // If high accuracy times out (code 3) or unavailable (code 2), retry with network/Wi-Fi positioning
          if (err.code === 3 || err.code === 2) {
            fallbackLowAccuracy()
          } else {
            const msg =
              err.code === 1
                ? 'Location permission denied — allow it in your browser to continue.'
                : 'Location unavailable right now.'
            setError(msg)
            reject(new Error(msg))
          }
        },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 10000 },
      )
    })
  }, [])

  const watch = useCallback(() => {
    if (!('geolocation' in navigator) || watchIdRef.current !== null) return

    const startLowAccuracyWatch = () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current)
      }
      watchIdRef.current = navigator.geolocation.watchPosition(
        (pos) => {
          setError('')
          setPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy })
        },
        (fallbackErr) => {
          setError(
            fallbackErr.code === 1
              ? 'Location permission denied.'
              : 'Location updates unavailable.'
          )
        },
        { enableHighAccuracy: false, timeout: 20000, maximumAge: 10000 },
      )
    }

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setError('')
        setPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy })
      },
      (err) => {
        if (err.code === 3 || err.code === 2) {
          startLowAccuracyWatch()
          return
        }
        setError(
          err.code === 1
            ? 'Location permission denied.'
            : 'Location updates unavailable.'
        )
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 },
    )
    setWatching(true)
  }, [])

  const stopWatch = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current)
      watchIdRef.current = null
    }
    setWatching(false)
  }, [])

  useEffect(() => stopWatch, [stopWatch])

  return { position, error, watching, locate, watch, stopWatch }
}

import { useEffect, useRef, useState } from 'react'

// The fetch pattern both screens need, in one place.
//
// Screen 1 grew this inline in Phase 5: a state enum, a `cancelled` flag, a debounce, and
// a refetch that keeps the previous render instead of flashing a skeleton. Screen 2 needs
// exactly the same behaviour against a different address, so it is extracted here rather
// than copied - two copies would drift the moment one of them is fixed.
//
// The `cancelled` flag is load-bearing, not boilerplate. StrictMode double-invokes effects
// in development, and dragging the slider can outrun its own requests, so a late response
// must never overwrite a newer one.

export const LOADING = 'loading'
export const REFRESHING = 'refreshing'
export const READY = 'ready'
export const FAILED = 'failed'

export const GENERIC_FAILURE =
  'Could not load data. The server may be starting up or unavailable.'

/** The server's own sentence if it sent one, otherwise the generic message. */
export async function failureMessage(response) {
  try {
    const body = await response.json()
    if (body && typeof body.error === 'string') return body.error
  } catch {
    // Not JSON - fall through to the generic message.
  }
  return GENERIC_FAILURE
}

async function getJson(url) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(await failureMessage(response))
  return response.json()
}

/**
 * Fetch whenever `key` changes, holding the previous value while the next is in flight.
 *
 * `load` is called with no arguments and returns a promise; `key` is what decides a
 * refetch, so it must be a primitive (a URL, or a JSON string of the settings) rather
 * than an object, which would be a new reference on every render and loop forever.
 */
export function useLoader(key, load, { debounceMs = 0 } = {}) {
  const [data, setData] = useState(null)
  const [status, setStatus] = useState(LOADING)
  const [message, setMessage] = useState(null)
  const hasData = useRef(false)

  useEffect(() => {
    if (key === null || key === undefined) return undefined
    let cancelled = false

    // No delay for the first load; debounce only once there is something to keep.
    const timer = setTimeout(
      () => {
        if (hasData.current) setStatus(REFRESHING)

        load()
          .then((result) => {
            if (cancelled) return
            setData(result)
            hasData.current = true
            setMessage(null)
            setStatus(READY)
          })
          .catch((error) => {
            if (cancelled) return
            setMessage(error.message || GENERIC_FAILURE)
            setStatus(FAILED)
          })
      },
      hasData.current ? debounceMs : 0,
    )

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // `load` is recreated every render by design; `key` is what decides a refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, debounceMs])

  return { data, status, message }
}

export { getJson }

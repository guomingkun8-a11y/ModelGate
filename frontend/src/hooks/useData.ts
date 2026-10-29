import { useCallback, useEffect, useRef, useState } from 'react'
import type { DependencyList } from 'react'
import { errorMessage } from '../api/http'

export default function useData<T>(loader: () => Promise<T>, deps: DependencyList = []) {
  const loaderRef = useRef(loader)
  loaderRef.current = loader
  const generation = useRef(0)
  const mounted = useRef(false)
  const [data, setData] = useState<T>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    const current = ++generation.current
    if (mounted.current) { setLoading(true); setError('') }
    try {
      const next = await loaderRef.current()
      if (mounted.current && current === generation.current) setData(next)
    } catch (reason) {
      if (mounted.current && current === generation.current) setError(errorMessage(reason))
    } finally {
      if (mounted.current && current === generation.current) setLoading(false)
    }
  }, [])
  useEffect(() => {
    mounted.current = true
    void refresh()
    const listener = () => { void refresh() }
    window.addEventListener('modelgate:refresh', listener)
    return () => {
      mounted.current = false
      generation.current++
      window.removeEventListener('modelgate:refresh', listener)
    }
  }, [refresh, ...deps])
  return { data, loading, error, refresh }
}

export { useData }

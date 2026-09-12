import { useCallback, useEffect, useRef, useState } from 'react'
import { listNodes } from '../services/nodesApi'
import { mapApiNodeToView, NodeRole, NodeView } from '../types/node'

interface UseNodesResult {
  nodes: NodeView[]
  loading: boolean
  error: string | null
  errorDetail: string | null
  refresh: () => void
}

/**
 * Loads nodes for a given role ('iran' | 'foreign') and refreshes them
 * periodically. No WebSocket endpoint for node status is documented yet
 * (see NOSRAT_BACKEND_CONTRACT.md), so this uses a conservative 10s poll
 * instead of a tight loop.
 */
export function useNodes(role: NodeRole): UseNodesResult {
  const [nodes, setNodes] = useState<NodeView[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorDetail, setErrorDetail] = useState<string | null>(null)
  const isFirstLoad = useRef(true)

  const load = useCallback(async () => {
    try {
      const apiNodes = await listNodes()
      const filtered = apiNodes
        .filter((n) => (role === 'foreign' ? n.metadata?.role === 'foreign' : n.metadata?.role !== 'foreign'))
        .map(mapApiNodeToView)
      setNodes(filtered)
      setError(null)
      setErrorDetail(null)
    } catch (err: any) {
      setError('Could not load nodes')
      setErrorDetail(err?.response?.data?.detail || err?.message || String(err))
    } finally {
      if (isFirstLoad.current) {
        setLoading(false)
        isFirstLoad.current = false
      }
    }
  }, [role])

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [load])

  return { nodes, loading, error, errorDetail, refresh: load }
}

import api from '../api/client'
import type { ApiNode, SSHNodeDraft, InstallProgressEvent } from '../types/node'

/**
 * Nodes service layer.
 *
 * Functions in the "Existing / working" section call real endpoints already
 * implemented by the panel backend today.
 *
 * Functions in the "SSH remote install (contract)" section call the endpoints
 * documented in NOSRAT_BACKEND_CONTRACT.md, which do not exist on the backend
 * yet. Per project policy we do NOT fake their behaviour: calling them against
 * a backend that hasn't implemented the contract will reject/404, and callers
 * must surface that as a real error state — never a fabricated success.
 */

// ---------- Existing / working (CA-certificate based registration) ----------

export async function listNodes(): Promise<ApiNode[]> {
  const res = await api.get<ApiNode[]>('/nodes')
  return res.data
}

export async function deleteNode(id: string): Promise<void> {
  await api.delete(`/nodes/${id}`)
}

export async function registerNode(payload: {
  name: string
  ip_address: string
  api_port: number
  role?: 'iran' | 'foreign'
}): Promise<ApiNode> {
  const { role, ...rest } = payload
  const res = await api.post<ApiNode>('/nodes', { ...rest, metadata: role ? { role } : {} })
  return res.data
}

export async function fetchCACertificate(): Promise<string> {
  const res = await api.get('/panel/ca', { responseType: 'text', headers: { Accept: 'text/plain' } })
  return res.data
}

export async function downloadCACertificate(): Promise<Blob> {
  const res = await api.get('/panel/ca?download=true', { responseType: 'blob' })
  return res.data
}

export async function fetchServerCACertificate(): Promise<string> {
  const res = await api.get('/panel/ca/server', { responseType: 'text', headers: { Accept: 'text/plain' } })
  return res.data
}

export async function downloadServerCACertificate(): Promise<Blob> {
  const res = await api.get('/panel/ca/server?download=true', { responseType: 'blob' })
  return res.data
}

// ---------- SSH remote install (contract — see NOSRAT_BACKEND_CONTRACT.md) ----------

export interface SSHTestResult {
  ok: boolean
  osFamily?: string
  osVersion?: string
  message?: string
}

/** POST /nodes/ssh/test-connection — validates reachability + auth before installing. */
export async function testSSHConnection(draft: SSHNodeDraft): Promise<SSHTestResult> {
  const { password, privateKey, passphrase, ...safeDraft } = draft
  const res = await api.post<SSHTestResult>('/nodes/ssh/test-connection', {
    ...safeDraft,
    password,
    private_key: privateKey,
    passphrase,
  })
  return res.data
}

export interface SSHInstallJob {
  jobId: string
  nodeId?: string
}

/** POST /nodes/ssh/install — kicks off remote agent installation, returns a job id to track. */
export async function startSSHInstall(draft: SSHNodeDraft): Promise<SSHInstallJob> {
  const { password, privateKey, passphrase, ...safeDraft } = draft
  const res = await api.post<SSHInstallJob>('/nodes/ssh/install', {
    ...safeDraft,
    password,
    private_key: privateKey,
    passphrase,
  })
  return res.data
}

/**
 * Subscribes to real-time install progress for a job.
 * Prefers a WebSocket stream at `/ws/nodes/install/:jobId`; if the socket
 * cannot be opened (backend doesn't implement it yet), falls back to
 * polling `GET /nodes/ssh/install/:jobId` every 2s. Returns an unsubscribe fn.
 */
export function subscribeInstallProgress(
  jobId: string,
  onEvent: (event: InstallProgressEvent) => void,
  onError: (error: unknown) => void
): () => void {
  let closed = false
  let pollHandle: ReturnType<typeof setInterval> | null = null
  let socket: WebSocket | null = null

  const startPolling = () => {
    pollHandle = setInterval(async () => {
      try {
        const res = await api.get<InstallProgressEvent>(`/nodes/ssh/install/${jobId}`)
        if (!closed) onEvent(res.data)
        if (!closed && (res.data.stage === 'completed' || res.data.stage === 'failed') && pollHandle) {
          clearInterval(pollHandle)
        }
      } catch (err) {
        if (!closed) onError(err)
        if (pollHandle) clearInterval(pollHandle)
      }
    }, 2000)
  }

  try {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    socket = new WebSocket(`${proto}://${window.location.host}/ws/nodes/install/${jobId}`)
    socket.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as InstallProgressEvent
        if (!closed) onEvent(data)
      } catch (err) {
        if (!closed) onError(err)
      }
    }
    socket.onerror = () => {
      socket?.close()
      if (!closed) startPolling()
    }
  } catch (err) {
    startPolling()
  }

  return () => {
    closed = true
    socket?.close()
    if (pollHandle) clearInterval(pollHandle)
  }
}

/** POST /nodes/:id/test-connection — re-check reachability of an already-registered node. */
export async function testExistingNodeConnection(id: string): Promise<SSHTestResult> {
  const res = await api.post<SSHTestResult>(`/nodes/${id}/test-connection`)
  return res.data
}

/** POST /nodes/:id/restart */
export async function restartNode(id: string): Promise<void> {
  await api.post(`/nodes/${id}/restart`)
}

/** POST /nodes/:id/reinstall */
export async function reinstallNode(id: string): Promise<void> {
  await api.post(`/nodes/${id}/reinstall`)
}

/** POST /nodes/:id/update */
export async function updateNode(id: string): Promise<void> {
  await api.post(`/nodes/${id}/update`)
}

/** GET /nodes/:id/logs */
export async function fetchNodeLogs(id: string): Promise<string[]> {
  const res = await api.get<{ lines: string[] }>(`/nodes/${id}/logs`)
  return res.data.lines
}

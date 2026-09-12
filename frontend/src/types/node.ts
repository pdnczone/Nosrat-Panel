/**
 * Node domain types.
 *
 * `ApiNode` mirrors exactly what the current Nosrat panel backend returns from
 * `GET /nodes` today (mTLS / CA-certificate based self-registration).
 *
 * `NodeResource`, `NodeAuthMethod` and the SSH-install request/response types
 * describe the shape the *frontend* expects once the backend gains SSH-based
 * remote installation (see NOSRAT_BACKEND_CONTRACT.md). None of these are
 * invented data — they are the documented contract the UI is built against.
 * Until the backend implements them, calls using these types will fail with
 * a real network/HTTP error, which the UI surfaces via `ErrorState` rather
 * than pretending to succeed.
 */

export type NodeRole = 'iran' | 'foreign'

export type ConnectionStatus = 'connected' | 'connecting' | 'reconnecting' | 'failed' | 'unknown'

/** Shape returned today by GET /nodes (see backend `node/` service). */
export interface ApiNode {
  id: string
  name: string
  fingerprint: string
  status: string
  registered_at: string
  last_seen: string
  metadata: {
    role?: NodeRole
    connection_status?: ConnectionStatus
    ip_address?: string
    [key: string]: unknown
  }
}

/** Live resource snapshot — only populated when the backend/agent reports it. */
export interface NodeResources {
  cpuPercent?: number
  memoryPercent?: number
  memoryUsedGb?: number
  memoryTotalGb?: number
  diskPercent?: number
  diskUsedGb?: number
  diskTotalGb?: number
  uptimeSeconds?: number
}

export type NodeAuthMethod = 'password' | 'private_key'

/** Step 1 + 2 of the Add Node (SSH) wizard. */
export interface SSHNodeDraft {
  name: string
  host: string
  sshPort: number
  username: string
  authMethod: NodeAuthMethod
  password?: string
  privateKey?: string
  passphrase?: string
  role: NodeRole
}

export type InstallStage =
  | 'connecting'
  | 'authenticating'
  | 'checking_os'
  | 'checking_requirements'
  | 'downloading'
  | 'installing'
  | 'configuring'
  | 'starting_service'
  | 'verifying'
  | 'completed'
  | 'failed'

export interface InstallProgressEvent {
  stage: InstallStage
  message: string
  progressPercent: number
  timestamp: string
}

/** Normalized, UI-friendly view of a node used across pages/components. */
export interface NodeView {
  id: string
  name: string
  fingerprint: string
  role: NodeRole
  connectionStatus: ConnectionStatus
  ipAddress?: string
  registeredAt: string
  lastSeen: string
  resources?: NodeResources
  os?: string
  installedVersion?: string
}

export function mapApiNodeToView(node: ApiNode): NodeView {
  return {
    id: node.id,
    name: node.name,
    fingerprint: node.fingerprint,
    role: (node.metadata?.role as NodeRole) ?? 'iran',
    connectionStatus: (node.metadata?.connection_status as ConnectionStatus) ?? 'unknown',
    ipAddress: node.metadata?.ip_address as string | undefined,
    registeredAt: node.registered_at,
    lastSeen: node.last_seen,
    // Resources, OS and version are not part of the current API response.
    // They stay undefined (and are rendered as "Requires agent support")
    // until the backend contract in section "Node resource reporting" ships.
    resources: undefined,
    os: undefined,
    installedVersion: undefined,
  }
}

export function connectionStatusToLive(status: ConnectionStatus): 'online' | 'connecting' | 'offline' | 'unknown' {
  switch (status) {
    case 'connected':
      return 'online'
    case 'connecting':
    case 'reconnecting':
      return 'connecting'
    case 'failed':
      return 'offline'
    default:
      return 'unknown'
  }
}

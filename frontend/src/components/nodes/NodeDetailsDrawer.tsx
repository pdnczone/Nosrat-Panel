import { useState } from 'react'
import { RotateCw, RefreshCcw, DownloadCloud, Trash2, Wifi, Info } from 'lucide-react'
import Drawer from '../ui/Drawer'
import Tabs from '../ui/Tabs'
import Badge from '../ui/Badge'
import StatusDot from '../ui/StatusDot'
import ConfirmDialog from '../ui/ConfirmDialog'
import Button from '../ui/Button'
import { NodeView, connectionStatusToLive } from '../../types/node'
import { deleteNode, restartNode, reinstallNode, updateNode, testExistingNodeConnection } from '../../services/nodesApi'
import { useToast } from '../ui/Toast'

interface NodeDetailsDrawerProps {
  node: NodeView | null
  onClose: () => void
  onDeleted: () => void
}

type TabId = 'overview' | 'resources' | 'tunnel' | 'logs' | 'actions'

const NotWiredHint = ({ endpoint }: { endpoint: string }) => (
  <div className="flex items-start gap-2 rounded-xl bg-secondary/50 p-3 text-xs text-muted-foreground">
    <Info size={14} className="mt-0.5 shrink-0" />
    <span>
      Requires agent support. The frontend calls <code>{endpoint}</code>; see{' '}
      <code>NOSRAT_BACKEND_CONTRACT.md</code>.
    </span>
  </div>
)

const NodeDetailsDrawer = ({ node, onClose, onDeleted }: NodeDetailsDrawerProps) => {
  const [tab, setTab] = useState<TabId>('overview')
  const [confirmRemove, setConfirmRemove] = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const { show } = useToast()

  if (!node) return null
  const live = connectionStatusToLive(node.connectionStatus)

  const runAction = async (key: string, fn: () => Promise<void>, successMsg: string) => {
    setBusyAction(key)
    setActionError(null)
    try {
      await fn()
      show(successMsg, 'success')
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err?.message || 'This action is not supported by the backend yet.')
    } finally {
      setBusyAction(null)
    }
  }

  const handleRemove = async () => {
    setBusyAction('remove')
    try {
      await deleteNode(node.id)
      show('Node removed', 'success')
      setConfirmRemove(false)
      onDeleted()
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err?.message || 'Failed to remove node')
    } finally {
      setBusyAction(null)
    }
  }

  return (
    <>
      <Drawer open={!!node} onClose={onClose} title={node.name} subtitle={node.ipAddress ?? node.fingerprint.slice(0, 16) + '…'}>
        <div className="mb-5 flex items-center justify-between">
          <StatusDot status={live} />
          <Badge tone={node.role === 'iran' ? 'brand' : 'neutral'}>{node.role === 'iran' ? 'Iran' : 'Foreign'}</Badge>
        </div>

        <Tabs
          tabs={[
            { id: 'overview', label: 'Overview' },
            { id: 'resources', label: 'Resources' },
            { id: 'tunnel', label: 'Tunnel' },
            { id: 'logs', label: 'Logs' },
            { id: 'actions', label: 'Actions' },
          ]}
          active={tab}
          onChange={(id) => setTab(id as TabId)}
        />

        <div className="mt-5">
          {tab === 'overview' && (
            <dl className="grid grid-cols-2 gap-y-3 text-sm">
              <dt className="text-muted-foreground">Status</dt>
              <dd className="text-foreground capitalize">{node.connectionStatus}</dd>
              <dt className="text-muted-foreground">IP address</dt>
              <dd className="text-foreground">{node.ipAddress ?? 'N/A'}</dd>
              <dt className="text-muted-foreground">OS</dt>
              <dd className="text-foreground">{node.os ?? '—'}</dd>
              <dt className="text-muted-foreground">Installed version</dt>
              <dd className="text-foreground">{node.installedVersion ?? '—'}</dd>
              <dt className="text-muted-foreground">Registered</dt>
              <dd className="text-foreground">{new Date(node.registeredAt).toLocaleString()}</dd>
              <dt className="text-muted-foreground">Last seen</dt>
              <dd className="text-foreground">{new Date(node.lastSeen).toLocaleString()}</dd>
              <dt className="text-muted-foreground">Fingerprint</dt>
              <dd className="truncate font-mono text-xs text-foreground" title={node.fingerprint}>
                {node.fingerprint}
              </dd>
            </dl>
          )}

          {tab === 'resources' && (
            <div className="space-y-3">
              {node.resources ? (
                <div className="text-sm text-foreground">CPU {node.resources.cpuPercent}% · RAM {node.resources.memoryPercent}%</div>
              ) : (
                <NotWiredHint endpoint="GET /nodes/:id/status" />
              )}
            </div>
          )}

          {tab === 'tunnel' && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Active tunnels for this node are shown on the Tunnels page, filtered by node — this drawer will surface a
                live summary here once <code>GET /nodes/:id/status</code> reports tunnel counts.
              </p>
              <NotWiredHint endpoint="GET /nodes/:id/status" />
            </div>
          )}

          {tab === 'logs' && (
            <div className="space-y-3">
              <NotWiredHint endpoint="GET /nodes/:id/logs" />
            </div>
          )}

          {tab === 'actions' && (
            <div className="space-y-3">
              {actionError && (
                <div className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">{actionError}</div>
              )}
              <Button
                variant="secondary"
                className="w-full justify-start"
                icon={<Wifi size={16} />}
                loading={busyAction === 'test'}
                onClick={() => runAction('test', async () => { await testExistingNodeConnection(node.id) }, 'Connection OK')}
              >
                Test Connection
              </Button>
              <Button
                variant="secondary"
                className="w-full justify-start"
                icon={<RotateCw size={16} />}
                loading={busyAction === 'restart'}
                onClick={() => runAction('restart', () => restartNode(node.id), 'Restart requested')}
              >
                Restart Node
              </Button>
              <Button
                variant="secondary"
                className="w-full justify-start"
                icon={<DownloadCloud size={16} />}
                loading={busyAction === 'update'}
                onClick={() => runAction('update', () => updateNode(node.id), 'Update requested')}
              >
                Update Node
              </Button>
              <Button
                variant="secondary"
                className="w-full justify-start"
                icon={<RefreshCcw size={16} />}
                loading={busyAction === 'reinstall'}
                onClick={() => runAction('reinstall', () => reinstallNode(node.id), 'Reinstall requested')}
              >
                Reinstall Node
              </Button>
              <Button
                variant="danger"
                className="w-full justify-start"
                icon={<Trash2 size={16} />}
                onClick={() => setConfirmRemove(true)}
              >
                Remove Node
              </Button>
            </div>
          )}
        </div>
      </Drawer>

      <ConfirmDialog
        open={confirmRemove}
        title="Remove this node?"
        description={`${node.name} will stop receiving traffic immediately and its tunnels will go offline. This can't be undone.`}
        confirmLabel="Remove Node"
        loading={busyAction === 'remove'}
        onConfirm={handleRemove}
        onCancel={() => setConfirmRemove(false)}
      />
    </>
  )
}

export default NodeDetailsDrawer

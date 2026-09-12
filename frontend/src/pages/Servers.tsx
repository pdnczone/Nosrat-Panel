import { useEffect, useState } from 'react'
import { Plus, Copy, Download, Globe, ChevronDown, Check } from 'lucide-react'
import { useLanguage } from '../contexts/LanguageContext'
import { useToast } from '../components/ui/Toast'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import StatusDot from '../components/ui/StatusDot'
import Modal from '../components/ui/Modal'
import { EmptyState, ErrorState, SkeletonCard } from '../components/ui/States'
import AddNodeSSHWizard from '../components/nodes/AddNodeSSHWizard'
import NodeDetailsDrawer from '../components/nodes/NodeDetailsDrawer'
import { useNodes } from '../hooks/useNodes'
import { connectionStatusToLive, NodeView } from '../types/node'
import { fetchServerCACertificate, downloadServerCACertificate, registerNode } from '../services/nodesApi'

const Servers = () => {
  const { t } = useLanguage()
  const { show } = useToast()
  const { nodes, loading, error, errorDetail, refresh } = useNodes('foreign')

  const [addMenuOpen, setAddMenuOpen] = useState(false)
  const [showRegisterModal, setShowRegisterModal] = useState(false)
  const [showSSHWizard, setShowSSHWizard] = useState(false)
  const [showCertModal, setShowCertModal] = useState(false)
  const [certContent, setCertContent] = useState('')
  const [certLoading, setCertLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [selectedNode, setSelectedNode] = useState<NodeView | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('add') === 'true') {
      setShowRegisterModal(true)
      window.history.replaceState({}, '', '/servers')
    }
  }, [])

  const openCA = async () => {
    setShowCertModal(true)
    setCertLoading(true)
    try {
      const text = await fetchServerCACertificate()
      if (!text || text.trim().length === 0) throw new Error('Certificate is empty.')
      setCertContent(text)
    } catch (err: any) {
      show(err?.response?.data?.detail || err.message || 'Failed to fetch CA certificate', 'error')
      setShowCertModal(false)
    } finally {
      setCertLoading(false)
    }
  }

  const download = async () => {
    try {
      const blob = await downloadServerCACertificate()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'ca-server.crt')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch {
      show('Failed to download CA certificate', 'error')
    }
  }

  const copyCert = async () => {
    await navigator.clipboard.writeText(certContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="w-full max-w-7xl mx-auto">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">{t.servers.title}</h1>
          <p className="mt-1 text-muted-foreground">{t.servers.subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" onClick={openCA} icon={<Copy size={16} />}>
            {t.servers.viewCACertificate}
          </Button>
          <Button variant="secondary" onClick={download} icon={<Download size={16} />}>
            {t.servers.downloadCA}
          </Button>
          <div className="relative">
            <Button onClick={() => setAddMenuOpen((v) => !v)} icon={<Plus size={18} />}>
              {t.dashboard.addServer}
              <ChevronDown size={14} />
            </Button>
            {addMenuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setAddMenuOpen(false)} />
                <div className="glass-panel-strong absolute end-0 z-20 mt-2 w-64 rounded-xl p-1.5 animate-fade-in-up">
                  <button
                    className="flex w-full flex-col items-start rounded-lg px-3 py-2.5 text-start hover:bg-secondary/60"
                    onClick={() => { setAddMenuOpen(false); setShowSSHWizard(true) }}
                  >
                    <span className="text-sm font-medium text-foreground">Add Server via SSH</span>
                    <span className="text-xs text-muted-foreground">Install the agent remotely (needs backend support)</span>
                  </button>
                  <button
                    className="flex w-full flex-col items-start rounded-lg px-3 py-2.5 text-start hover:bg-secondary/60"
                    onClick={() => { setAddMenuOpen(false); setShowRegisterModal(true) }}
                  >
                    <span className="text-sm font-medium text-foreground">Register via CA Certificate</span>
                    <span className="text-xs text-muted-foreground">The server installs itself and registers with the panel</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : error ? (
        <ErrorState message={error} detail={errorDetail ?? undefined} onRetry={refresh} />
      ) : nodes.length === 0 ? (
        <EmptyState
          icon={<Globe size={24} />}
          title="No foreign servers yet"
          description="Add a server via SSH or register one using the CA certificate flow to get started."
          action={<Button onClick={() => setShowSSHWizard(true)} icon={<Plus size={16} />}>{t.dashboard.addServer}</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {nodes.map((node) => (
            <Card key={node.id} hover className="cursor-pointer p-5" onClick={() => setSelectedNode(node)}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="brand-mark h-11 w-11">
                    <Globe size={20} />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">{node.name}</p>
                    <p className="text-xs text-muted-foreground">{node.ipAddress ?? 'No IP reported'}</p>
                  </div>
                </div>
                <Badge tone="neutral">Foreign</Badge>
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-border/60 pt-3">
                <StatusDot status={connectionStatusToLive(node.connectionStatus)} />
                <span className="text-xs text-muted-foreground">
                  Seen {new Date(node.lastSeen).toLocaleTimeString()}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={showRegisterModal} onClose={() => setShowRegisterModal(false)} title={t.dashboard.addServer} size="sm">
        <RegisterServerForm
          onSuccess={() => { setShowRegisterModal(false); refresh() }}
          onCancel={() => setShowRegisterModal(false)}
        />
      </Modal>

      <AddNodeSSHWizard open={showSSHWizard} role="foreign" onClose={() => setShowSSHWizard(false)} onCompleted={refresh} />

      <NodeDetailsDrawer node={selectedNode} onClose={() => setSelectedNode(null)} onDeleted={() => { setSelectedNode(null); refresh() }} />

      <Modal
        open={showCertModal}
        onClose={() => setShowCertModal(false)}
        title="Foreign Server CA Certificate"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowCertModal(false)}>Close</Button>
            <Button onClick={copyCert} disabled={certLoading || !certContent} icon={copied ? <Check size={16} /> : <Copy size={16} />}>
              {copied ? 'Copied!' : 'Copy Certificate'}
            </Button>
          </>
        }
      >
        <div className="mb-4 rounded-xl bg-secondary/50 p-3 text-sm text-muted-foreground">
          <strong className="text-foreground">Foreign server installation:</strong> copy this certificate — you'll be
          asked to paste it during installation.
        </div>
        {certLoading ? (
          <div className="flex h-40 items-center justify-center text-muted-foreground">Loading certificate…</div>
        ) : (
          <textarea readOnly value={certContent} className="field-input min-h-[280px] resize-none font-mono text-xs" />
        )}
      </Modal>
    </div>
  )
}

const RegisterServerForm = ({ onSuccess, onCancel }: { onSuccess: () => void; onCancel: () => void }) => {
  const { show } = useToast()
  const [name, setName] = useState('')
  const [ipAddress, setIpAddress] = useState('')
  const [apiPort, setApiPort] = useState('8888')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await registerNode({ name, ip_address: ipAddress, api_port: parseInt(apiPort) || 8888, role: 'foreign' })
      show('Server registered', 'success')
      onSuccess()
    } catch (err: any) {
      show(err?.response?.data?.detail || 'Failed to add server', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="field-label">Server Name</label>
        <input className="field-input" value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div>
        <label className="field-label">IP Address</label>
        <input
          className="field-input"
          value={ipAddress}
          onChange={(e) => setIpAddress(e.target.value)}
          placeholder="e.g. 192.168.1.100"
          required
        />
      </div>
      <div>
        <label className="field-label">API Port</label>
        <input
          type="number"
          className="field-input"
          value={apiPort}
          onChange={(e) => setApiPort(e.target.value)}
          min={1}
          max={65535}
          required
        />
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={submitting}>Register Server</Button>
      </div>
    </form>
  )
}

export default Servers

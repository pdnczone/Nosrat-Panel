import { useState } from 'react'
import { Server, KeyRound, Wifi, Download, Loader2, ShieldCheck, PartyPopper, Info } from 'lucide-react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import ProgressSteps from '../ui/ProgressSteps'
import SecretField from '../ui/SecretField'
import { ErrorState } from '../ui/States'
import { NodeAuthMethod, NodeRole, SSHNodeDraft, InstallProgressEvent, InstallStage } from '../../types/node'
import { testSSHConnection, startSSHInstall, subscribeInstallProgress, SSHTestResult } from '../../services/nodesApi'

const STEP_LABELS = [
  'Server Info',
  'Authentication',
  'Connection Test',
  'Install',
  'Progress',
  'Verify',
  'Completed',
]

const STAGE_LABELS: Record<InstallStage, string> = {
  connecting: 'Connecting…',
  authenticating: 'Authenticating…',
  checking_os: 'Checking OS…',
  checking_requirements: 'Checking requirements…',
  downloading: 'Downloading Nosrat Node…',
  installing: 'Installing…',
  configuring: 'Configuring…',
  starting_service: 'Starting service…',
  verifying: 'Verifying…',
  completed: 'Node connected',
  failed: 'Installation failed',
}

interface AddNodeSSHWizardProps {
  open: boolean
  role: NodeRole
  onClose: () => void
  onCompleted: () => void
}

const emptyDraft = (role: NodeRole): SSHNodeDraft => ({
  name: '',
  host: '',
  sshPort: 22,
  username: 'root',
  authMethod: 'password',
  password: '',
  privateKey: '',
  passphrase: '',
  role,
})

/**
 * Add Node → SSH install wizard.
 *
 * This talks to endpoints documented in NOSRAT_BACKEND_CONTRACT.md
 * (`/nodes/ssh/test-connection`, `/nodes/ssh/install`, install progress
 * stream) which are not implemented by the current backend. Every action
 * here performs a real network call — there is no simulated/mocked success
 * path. Until the backend ships the contract, users will see a genuine
 * "not implemented yet" error at the Connection Test step, which is
 * expected and intentional.
 */
const AddNodeSSHWizard = ({ open, role, onClose, onCompleted }: AddNodeSSHWizardProps) => {
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<SSHNodeDraft>(() => emptyDraft(role))
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<SSHTestResult | null>(null)
  const [testError, setTestError] = useState<{ message: string; detail?: string } | null>(null)
  const [installing, setInstalling] = useState(false)
  const [installError, setInstallError] = useState<{ message: string; detail?: string } | null>(null)
  const [progress, setProgress] = useState<InstallProgressEvent | null>(null)

  const reset = () => {
    setStep(0)
    setDraft(emptyDraft(role))
    setTesting(false)
    setTestResult(null)
    setTestError(null)
    setInstalling(false)
    setInstallError(null)
    setProgress(null)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const update = <K extends keyof SSHNodeDraft>(key: K, value: SSHNodeDraft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }))

  const runConnectionTest = async () => {
    setTesting(true)
    setTestError(null)
    setTestResult(null)
    try {
      const result = await testSSHConnection(draft)
      setTestResult(result)
    } catch (err: any) {
      setTestError({
        message: 'SSH connection failed',
        detail: err?.response?.data?.detail || err?.message || String(err),
      })
    } finally {
      setTesting(false)
    }
  }

  const runInstall = async () => {
    setInstalling(true)
    setInstallError(null)
    setStep(4)
    try {
      const job = await startSSHInstall(draft)
      subscribeInstallProgress(
        job.jobId,
        (event) => {
          setProgress(event)
          if (event.stage === 'completed') {
            setInstalling(false)
            setStep(6)
          }
          if (event.stage === 'failed') {
            setInstalling(false)
            setInstallError({ message: event.message || 'Installation failed' })
          }
        },
        (err: any) => {
          setInstalling(false)
          setInstallError({
            message: 'Lost connection to the installation stream',
            detail: err?.message || String(err),
          })
        }
      )
    } catch (err: any) {
      setInstalling(false)
      setInstallError({
        message: 'Could not start installation',
        detail: err?.response?.data?.detail || err?.message || String(err),
      })
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title="Add Node via SSH" size="lg">
      <div className="mb-6">
        <ProgressSteps steps={STEP_LABELS} currentIndex={step} />
      </div>

      {step === 0 && (
        <div className="space-y-4 animate-fade-in-up">
          <div>
            <label className="field-label">Node name</label>
            <input
              className="field-input"
              placeholder="e.g. iran-node-2"
              value={draft.name}
              onChange={(e) => update('name', e.target.value)}
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="field-label">Host / IP address</label>
              <input
                className="field-input"
                placeholder="203.0.113.10"
                value={draft.host}
                onChange={(e) => update('host', e.target.value)}
              />
            </div>
            <div>
              <label className="field-label">SSH Port</label>
              <input
                type="number"
                className="field-input"
                value={draft.sshPort}
                onChange={(e) => update('sshPort', Number(e.target.value) || 22)}
              />
            </div>
          </div>
          <div>
            <label className="field-label">Role</label>
            <div className="flex gap-2">
              {(['iran', 'foreign'] as NodeRole[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => update('role', r)}
                  className={draft.role === r ? 'btn-primary flex-1 capitalize' : 'btn-secondary flex-1 capitalize'}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4 animate-fade-in-up">
          <div>
            <label className="field-label">Username</label>
            <input
              className="field-input"
              value={draft.username}
              onChange={(e) => update('username', e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Authentication method</label>
            <div className="flex gap-2">
              {(['password', 'private_key'] as NodeAuthMethod[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => update('authMethod', m)}
                  className={draft.authMethod === m ? 'btn-primary flex-1' : 'btn-secondary flex-1'}
                >
                  {m === 'password' ? 'Password' : 'SSH Private Key'}
                </button>
              ))}
            </div>
          </div>
          {draft.authMethod === 'password' ? (
            <SecretField
              label="Password"
              placeholder="••••••••"
              value={draft.password}
              onChange={(e) => update('password', e.target.value)}
            />
          ) : (
            <>
              <div>
                <label className="field-label">Private key</label>
                <textarea
                  className="field-input font-mono text-xs"
                  rows={5}
                  placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                  value={draft.privateKey}
                  onChange={(e) => update('privateKey', e.target.value)}
                />
                <p className="field-hint">Stored only in memory for this session. Never written to disk or logs.</p>
              </div>
              <SecretField
                label="Passphrase (optional)"
                value={draft.passphrase}
                onChange={(e) => update('passphrase', e.target.value)}
              />
            </>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="animate-fade-in-up">
          <div className="flex flex-col items-center gap-4 py-6 text-center">
            {testing ? (
              <>
                <Loader2 className="animate-spin text-brand" size={32} style={{ color: 'hsl(var(--brand-from))' }} />
                <p className="text-sm text-muted-foreground">Testing connection to {draft.host}…</p>
              </>
            ) : testResult?.ok ? (
              <>
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-success/15 text-success">
                  <Wifi size={24} />
                </div>
                <div>
                  <p className="font-semibold text-foreground">Connection successful</p>
                  <p className="text-sm text-muted-foreground">
                    {testResult.osFamily ? `${testResult.osFamily} ${testResult.osVersion ?? ''}` : 'Ready to install'}
                  </p>
                </div>
              </>
            ) : testError ? (
              <ErrorState message={testError.message} detail={testError.detail} onRetry={runConnectionTest} />
            ) : (
              <>
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary text-muted-foreground">
                  <Wifi size={24} />
                </div>
                <p className="text-sm text-muted-foreground">Run a connection test before installing.</p>
                <Button onClick={runConnectionTest}>Test Connection</Button>
              </>
            )}
          </div>
          {testError && (
            <div className="flex items-start gap-2 rounded-xl bg-secondary/50 p-3 text-xs text-muted-foreground">
              <Info size={14} className="mt-0.5 shrink-0" />
              <span>
                SSH-based installation requires backend support that hasn't shipped yet — see{' '}
                <code>NOSRAT_BACKEND_CONTRACT.md</code>. Registering nodes via the CA certificate flow works today.
              </span>
            </div>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4 animate-fade-in-up">
          <div className="glass-panel rounded-xl p-4 text-sm">
            <p className="mb-2 font-medium text-foreground">Ready to install Nosrat Node</p>
            <dl className="grid grid-cols-2 gap-y-1.5 text-muted-foreground">
              <dt>Name</dt>
              <dd className="text-foreground">{draft.name || '—'}</dd>
              <dt>Host</dt>
              <dd className="text-foreground">{draft.host}:{draft.sshPort}</dd>
              <dt>Role</dt>
              <dd className="text-foreground capitalize">{draft.role}</dd>
              <dt>Auth</dt>
              <dd className="text-foreground">{draft.authMethod === 'password' ? 'Password' : 'Private key'}</dd>
            </dl>
          </div>
          {installError && <ErrorState message={installError.message} detail={installError.detail} onRetry={runInstall} />}
        </div>
      )}

      {step === 4 && (
        <div className="animate-fade-in-up space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="animate-spin" size={20} style={{ color: 'hsl(var(--brand-from))' }} />
            <p className="font-medium text-foreground">
              {progress ? STAGE_LABELS[progress.stage] : 'Starting installation…'}
            </p>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full brand-gradient-bg transition-all duration-500"
              style={{ width: `${progress?.progressPercent ?? 5}%` }}
            />
          </div>
          {installError && <ErrorState message={installError.message} detail={installError.detail} onRetry={runInstall} />}
        </div>
      )}

      {step === 5 && (
        <div className="flex flex-col items-center gap-3 py-8 text-center animate-fade-in-up">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-success/15 text-success">
            <ShieldCheck size={24} />
          </div>
          <p className="font-medium text-foreground">Verifying node connectivity…</p>
        </div>
      )}

      {step === 6 && (
        <div className="flex flex-col items-center gap-3 py-8 text-center animate-fade-in-up">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-success/15 text-success">
            <PartyPopper size={24} />
          </div>
          <p className="text-lg font-semibold text-foreground">Node connected</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            {draft.name || draft.host} has been installed and is now reporting to the panel.
          </p>
        </div>
      )}

      <div className="mt-8 flex justify-between border-t border-border/60 pt-5">
        <Button variant="ghost" onClick={handleClose}>
          {step === 6 ? 'Close' : 'Cancel'}
        </Button>
        <div className="flex gap-3">
          {step > 0 && step < 4 && (
            <Button variant="secondary" onClick={() => setStep((s) => s - 1)}>
              Back
            </Button>
          )}
          {step === 0 && (
            <Button onClick={() => setStep(1)} disabled={!draft.name || !draft.host} icon={<Server size={16} />}>
              Next
            </Button>
          )}
          {step === 1 && (
            <Button
              onClick={() => setStep(2)}
              disabled={draft.authMethod === 'password' ? !draft.password : !draft.privateKey}
              icon={<KeyRound size={16} />}
            >
              Next
            </Button>
          )}
          {step === 2 && (
            <Button onClick={() => setStep(3)} disabled={!testResult?.ok}>
              Next
            </Button>
          )}
          {step === 3 && (
            <Button onClick={runInstall} loading={installing} icon={<Download size={16} />}>
              Install Node
            </Button>
          )}
          {step === 6 && (
            <Button
              onClick={() => {
                onCompleted()
                handleClose()
              }}
            >
              Done
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}

export default AddNodeSSHWizard

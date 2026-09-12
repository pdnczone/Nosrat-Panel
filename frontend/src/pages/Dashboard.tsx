import { useEffect, useState } from 'react'
import { Server, Network, Cpu, MemoryStick, Plus, Activity as ActivityIcon, ShieldCheck, AlertTriangle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useLanguage } from '../contexts/LanguageContext'
import api from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { SkeletonCard } from '../components/ui/States'

interface Status {
  system: {
    cpu_percent: number
    memory_percent: number
    memory_total_gb: number
    memory_used_gb: number
  }
  tunnels: {
    total: number
    active: number
  }
  nodes: {
    total: number
    active: number
  }
}

const Dashboard = () => {
  const [status, setStatus] = useState<Status | null>(null)
  const [loading, setLoading] = useState(true)
  const { t } = useLanguage()

  useEffect(() => {
    const fetchData = async () => {
      try {
        const statusResponse = await api.get('/status')
        setStatus(statusResponse.data)
      } catch (error) {
        console.error('Failed to fetch data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  // Simple, transparent health heuristic derived from real reported metrics only.
  const health = (() => {
    if (!status) return null
    const { cpu_percent, memory_percent } = status.system
    if (cpu_percent >= 90 || memory_percent >= 90) return 'critical' as const
    if (cpu_percent >= 70 || memory_percent >= 70) return 'warning' as const
    return 'healthy' as const
  })()

  if (loading || !status) {
    return (
      <div className="w-full max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="skeleton h-8 w-56" />
          <div className="skeleton mt-2 h-4 w-72" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-7xl mx-auto" dir="ltr">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">{t.dashboard.title}</h1>
          <p className="mt-1 text-muted-foreground">{t.dashboard.subtitle}</p>
        </div>
        {health && (
          <Badge tone={health === 'healthy' ? 'success' : health === 'warning' ? 'warning' : 'danger'}>
            {health === 'healthy' ? <ShieldCheck size={14} /> : <AlertTriangle size={14} />}
            System {health === 'healthy' ? 'healthy' : health}
          </Badge>
        )}
      </div>

      <div className="mb-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title={t.dashboard.totalNodes}
          value={status.nodes.total}
          subtitle={`${status.nodes.active} ${t.dashboard.active}`}
          icon={Server}
        />
        <StatCard
          title={t.dashboard.totalTunnels}
          value={status.tunnels.total}
          subtitle={`${status.tunnels.active} ${t.dashboard.active}`}
          icon={Network}
        />
        <StatCard
          title={t.dashboard.cpuUsage}
          value={`${status.system.cpu_percent.toFixed(1)}%`}
          subtitle={t.dashboard.currentUsage}
          icon={Cpu}
        />
        <StatCard
          title={t.dashboard.memoryUsage}
          value={`${status.system.memory_used_gb.toFixed(1)} GB`}
          subtitle={`${status.system.memory_percent.toFixed(1)}% of ${status.system.memory_total_gb.toFixed(1)} GB`}
          icon={MemoryStick}
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <div className="mb-6 flex items-center gap-3">
            <div className="brand-mark h-10 w-10">
              <ActivityIcon size={18} />
            </div>
            <h2 className="text-lg font-semibold text-foreground">{t.dashboard.systemResources}</h2>
          </div>
          <div className="space-y-5">
            <ProgressBar label="CPU" value={status.system.cpu_percent} />
            <ProgressBar label="Memory" value={status.system.memory_percent} />
          </div>
        </Card>

        <Card className="p-6">
          <div className="mb-6 flex items-center gap-3">
            <div className="brand-mark h-10 w-10">
              <Plus size={18} />
            </div>
            <h2 className="text-lg font-semibold text-foreground">{t.dashboard.quickActions}</h2>
          </div>
          <div className="space-y-3">
            <Button className="w-full justify-center" onClick={() => (window.location.href = '/tunnels?create=true')}>
              {t.dashboard.createNewTunnel}
            </Button>
            <Button
              variant="secondary"
              className="w-full justify-center"
              onClick={() => (window.location.href = '/nodes?add=true')}
            >
              {t.dashboard.addNode}
            </Button>
            <Button
              variant="secondary"
              className="w-full justify-center"
              onClick={() => (window.location.href = '/servers?add=true')}
            >
              {t.dashboard.addServer}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: string | number
  subtitle: string
  icon: LucideIcon
}

const StatCard = ({ title, value, subtitle, icon: Icon }: StatCardProps) => {
  return (
    <Card hover className="p-5">
      <div className="mb-3 flex items-start justify-between">
        <div className="brand-mark h-11 w-11">
          <Icon size={20} />
        </div>
      </div>
      <h3 className="mb-1.5 text-sm font-medium text-muted-foreground">{title}</h3>
      <p className="mb-1 text-3xl font-bold text-foreground">{value}</p>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
    </Card>
  )
}

const ProgressBar = ({ label, value }: { label: string; value: number }) => {
  const percentage = Math.min(value, 100)
  const tone = percentage >= 90 ? 'bg-destructive' : percentage >= 70 ? 'bg-warning' : ''
  return (
    <div>
      <div className="mb-2.5 flex items-center justify-between text-sm">
        <span className="font-medium text-foreground/80">{label}</span>
        <span className="font-semibold text-foreground">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${tone || 'brand-gradient-bg'}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

export default Dashboard

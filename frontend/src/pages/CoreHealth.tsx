import { useState, useEffect } from 'react'
import { Activity, RefreshCw, Clock, CheckCircle2, XCircle, AlertCircle, Settings } from 'lucide-react'
import api from '../api/client'
import { useLanguage } from '../contexts/LanguageContext'

interface CoreHealth {
  core: string
  nodes_status: Record<string, {
    id: string
    name: string
    role: string
    status: string
    error_message?: string | null
  }>
  servers_status: Record<string, {
    id: string
    name: string
    role: string
    status: string
    error_message?: string | null
  }>
}

interface ResetConfig {
  core: string
  enabled: boolean
  interval_minutes: number
  last_reset: string | null
  next_reset: string | null
}

const CoreHealth = () => {
  const { t } = useLanguage()
  const [health, setHealth] = useState<CoreHealth[]>([])
  const [configs, setConfigs] = useState<ResetConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      const [healthRes, configsRes] = await Promise.all([
        api.get('/core-health/health'),
        api.get('/core-health/reset-config')
      ])
      setHealth(healthRes.data)
      setConfigs(configsRes.data)
    } catch (error) {
      console.error('Failed to fetch core health:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])


  const handleReset = async (core: string) => {
    if (!confirm(`Are you sure you want to reset ${core} core?`)) return
    
    setUpdating(core)
    try {
      await api.post(`/core-health/reset/${core}`)
      await fetchData()
    } catch (error) {
      console.error(`Failed to reset ${core}:`, error)
      alert(`Failed to reset ${core}`)
    } finally {
      setUpdating(null)
    }
  }

  const handleConfigUpdate = async (core: string, updates: Partial<ResetConfig>) => {
    setUpdating(core)
    try {
      await api.put(`/core-health/reset-config/${core}`, updates)
      await fetchData()
    } catch (error) {
      console.error(`Failed to update config for ${core}:`, error)
      alert(`Failed to update config`)
    } finally {
      setUpdating(null)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "text-green-500"
      case "connecting":
        return "text-yellow-500"
      case "reconnecting":
        return "text-yellow-500"
      case "failed":
        return "text-red-500"
      default:
        return "text-gray-500"
    }
  }

  const getStatusBgColor = (status: string) => {
    switch (status) {
      case "connected":
        return "bg-success/15 text-success"
      case "connecting":
        return "bg-warning/15 text-warning"
      case "reconnecting":
        return "bg-warning/15 text-warning"
      case "failed":
        return "bg-destructive/15 text-destructive"
      default:
        return "bg-secondary/60 text-gray-800 dark:text-gray-200"
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "connected":
        return <CheckCircle2 className="w-5 h-5 text-green-500" />
      case "connecting":
      case "reconnecting":
        return <AlertCircle className="w-5 h-5 text-yellow-500" />
      case "failed":
        return <XCircle className="w-5 h-5 text-red-500" />
      default:
        return <AlertCircle className="w-5 h-5 text-muted-foreground" />
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "connected":
        return "Connected"
      case "connecting":
        return "Connecting"
      case "reconnecting":
        return "Reconnecting"
      case "failed":
        return "Failed"
      default:
        return "Unknown"
    }
  }


  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="brand-mark mx-auto h-12 w-12 animate-pulse mb-4"></div>
          <p className="text-muted-foreground">{t.common.loading}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-foreground mb-2">{t.coreHealth.title}</h1>
        <p className="text-muted-foreground">{t.coreHealth.subtitle}</p>
      </div>

      <div className="space-y-6">
        {health.map((coreHealth) => {
          const config = configs.find(c => c.core === coreHealth.core)
          const nodeCount = Object.keys(coreHealth.nodes_status).length
          const serverCount = Object.keys(coreHealth.servers_status).length

          return (
            <div
              key={coreHealth.core}
              className="glass-panel rounded-lg shadow-sm border border-border/60 p-6"
            >
              <div className="mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-secondary/70 rounded-lg">
                    <Activity className="w-6 h-6 text-brand-accent" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-foreground capitalize">
                      {coreHealth.core}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {nodeCount} node(s), {serverCount} server(s)
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div>
                  <h3 className="text-sm font-medium text-foreground/90 mb-3">
                    Node Status
                  </h3>
                  <div className="space-y-2">
                    {Object.entries(coreHealth.nodes_status).map(([nodeId, nodeInfo]) => (
                      <div key={nodeId} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground truncate max-w-[200px]">
                            {nodeInfo.name || nodeId.substring(0, 8)}...
                          </span>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(nodeInfo.status)}
                            <span className={`text-sm font-medium ${getStatusColor(nodeInfo.status)}`}>
                              {getStatusText(nodeInfo.status)}
                            </span>
                          </div>
                        </div>
                        {nodeInfo.error_message && (
                          <p className="text-xs text-destructive ml-2">
                            {nodeInfo.error_message}
                          </p>
                        )}
                      </div>
                    ))}
                    {nodeCount === 0 && (
                      <span className="text-sm text-muted-foreground">No active nodes</span>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-medium text-foreground/90 mb-3">
                    Server Status
                  </h3>
                  <div className="space-y-2">
                    {serverCount === 0 ? (
                      <span className="text-sm text-muted-foreground">No active servers</span>
                    ) : (
                      Object.entries(coreHealth.servers_status).map(([serverId, serverInfo]) => (
                        <div key={serverId} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-muted-foreground truncate max-w-[200px]">
                              {serverInfo.name || serverId.substring(0, 8)}...
                            </span>
                            <div className="flex items-center gap-2">
                              {getStatusIcon(serverInfo.status)}
                              <span className={`text-sm font-medium ${getStatusColor(serverInfo.status)}`}>
                                {getStatusText(serverInfo.status)}
                              </span>
                            </div>
                          </div>
                          {serverInfo.error_message && (
                            <p className="text-xs text-destructive ml-2">
                              {serverInfo.error_message}
                            </p>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              <div className="border-t border-border/60 pt-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Clock className="w-5 h-5 text-muted-foreground" />
                    <h3 className="text-sm font-medium text-foreground/90">
                      Auto Reset Timer
                    </h3>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config?.enabled || false}
                      onChange={(e) => handleConfigUpdate(coreHealth.core, { enabled: e.target.checked })}
                      disabled={updating === coreHealth.core}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-secondary peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-ring/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-border after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-[hsl(var(--brand-from))] peer-checked:to-[hsl(var(--brand-to))]"></div>
                  </label>
                </div>

                {config?.enabled && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <label className="text-sm text-muted-foreground">
                        Interval (minutes):
                      </label>
                      <input
                        type="number"
                        min="1"
                        value={config.interval_minutes}
                        onChange={(e) => {
                          const minutes = parseInt(e.target.value)
                          if (minutes >= 1) {
                            handleConfigUpdate(coreHealth.core, { interval_minutes: minutes })
                          }
                        }}
                        disabled={updating === coreHealth.core}
                        className="w-20 px-2 py-1 text-sm border border-input rounded-md bg-background/60 text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between mt-4 pt-4 border-t border-border/60">
                  <button
                    onClick={() => handleReset(coreHealth.core)}
                    disabled={updating === coreHealth.core}
                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {updating === coreHealth.core ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        <span>Resetting...</span>
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-4 h-4" />
                        <span>Reset Now</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default CoreHealth


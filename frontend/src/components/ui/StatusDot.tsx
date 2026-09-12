export type LiveStatus = 'online' | 'connecting' | 'offline' | 'unknown'

const colorMap: Record<LiveStatus, string> = {
  online: 'text-success bg-success',
  connecting: 'text-warning bg-warning',
  offline: 'text-destructive bg-destructive',
  unknown: 'text-muted-foreground bg-muted-foreground',
}

const labelMap: Record<LiveStatus, string> = {
  online: 'Online',
  connecting: 'Connecting',
  offline: 'Offline',
  unknown: 'Unknown',
}

interface StatusDotProps {
  status: LiveStatus
  label?: string
  pulse?: boolean
  showLabel?: boolean
}

/** Small live-status indicator: solid dot + optional label, pulses for transitional states. */
const StatusDot = ({ status, label, pulse = status === 'connecting', showLabel = true }: StatusDotProps) => {
  const [textColor, bgColor] = colorMap[status].split(' ')
  return (
    <span className={`inline-flex items-center gap-2 text-sm ${textColor}`}>
      <span className={`status-dot ${bgColor} ${pulse ? 'status-dot-ping' : ''}`} />
      {showLabel && <span className="font-medium">{label ?? labelMap[status]}</span>}
    </span>
  )
}

export default StatusDot

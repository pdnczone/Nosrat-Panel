import { ReactNode, useState } from 'react'
import { Inbox, AlertCircle, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react'
import Button from './Button'

/** Shown when a list/page legitimately has no data yet. */
export const EmptyState = ({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) => (
  <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border py-16 text-center">
    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary/60 text-muted-foreground">
      {icon ?? <Inbox size={24} />}
    </div>
    <div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
    </div>
    {action}
  </div>
)

/** Shown when a request fails. Friendly message up front, technical detail behind a toggle. */
export const ErrorState = ({
  message,
  detail,
  onRetry,
}: {
  message: string
  detail?: string
  onRetry?: () => void
}) => {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 py-14 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/15 text-destructive">
        <AlertCircle size={24} />
      </div>
      <div>
        <h3 className="text-base font-semibold text-foreground">{message}</h3>
        {detail && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-1.5 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            {expanded ? 'Hide technical details' : 'Show technical details'}
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
        {expanded && detail && (
          <pre className="mt-2 max-w-md whitespace-pre-wrap rounded-lg bg-secondary/60 p-3 text-left text-xs text-muted-foreground">
            {detail}
          </pre>
        )}
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} icon={<RefreshCw size={15} />}>
          Try again
        </Button>
      )}
    </div>
  )
}

/** Rectangular shimmering placeholder for loading rows/cards. */
export const Skeleton = ({ className = '' }: { className?: string }) => (
  <div className={`skeleton ${className}`} />
)

export const SkeletonCard = () => (
  <div className="glass-card p-5">
    <Skeleton className="h-10 w-10 rounded-xl" />
    <Skeleton className="mt-4 h-4 w-2/3" />
    <Skeleton className="mt-2 h-6 w-1/3" />
  </div>
)

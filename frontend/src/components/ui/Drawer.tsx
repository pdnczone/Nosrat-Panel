import { ReactNode, useEffect } from 'react'
import { X } from 'lucide-react'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  subtitle?: ReactNode
  children: ReactNode
  widthClass?: string
}

/** Right-anchored (left in RTL) slide-over drawer, used for node/tunnel details. */
const Drawer = ({ open, onClose, title, subtitle, children, widthClass = 'max-w-xl' }: DrawerProps) => {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="scrim animate-fade-in" onClick={onClose} role="dialog" aria-modal="true">
      <div
        onClick={(e) => e.stopPropagation()}
        dir="ltr"
        className={`glass-panel-strong fixed inset-y-0 end-0 w-full ${widthClass} flex flex-col animate-slide-in-right rounded-none sm:rounded-s-3xl`}
      >
        <div className="flex items-start justify-between border-b border-border/60 px-6 py-5">
          <div>
            {title && <h2 className="text-lg font-semibold text-foreground">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="btn-icon" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  )
}

export default Drawer

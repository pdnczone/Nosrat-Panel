import { ReactNode, useEffect } from 'react'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
  closeOnOverlay?: boolean
}

const sizeClass: Record<NonNullable<ModalProps['size']>, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
}

/** Centered glass modal used for forms, confirmations, and detail popups. */
const Modal = ({ open, onClose, title, children, footer, size = 'md', closeOnOverlay = true }: ModalProps) => {
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
    <div
      className="scrim flex items-center justify-center p-4 animate-fade-in"
      onClick={closeOnOverlay ? onClose : undefined}
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={`glass-panel-strong w-full ${sizeClass[size]} max-h-[90vh] flex flex-col rounded-2xl animate-scale-in`}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-border/60 px-6 py-4">
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
            <button onClick={onClose} className="btn-icon" aria-label="Close">
              <X size={18} />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex items-center justify-end gap-3 border-t border-border/60 px-6 py-4">{footer}</div>}
      </div>
    </div>
  )
}

export default Modal

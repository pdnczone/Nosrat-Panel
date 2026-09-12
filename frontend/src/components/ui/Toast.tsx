import { createContext, useCallback, useContext, useState, ReactNode } from 'react'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'

type ToastKind = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

interface ToastContextType {
  show: (message: string, kind?: ToastKind) => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

const iconMap: Record<ToastKind, ReactNode> = {
  success: <CheckCircle2 size={18} className="text-success" />,
  error: <XCircle size={18} className="text-destructive" />,
  info: <Info size={18} className="text-brand" style={{ color: 'hsl(var(--brand-from))' }} />,
}

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const show = useCallback((message: string, kind: ToastKind = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, kind, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const dismiss = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id))

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 end-4 z-[100] flex w-full max-w-sm flex-col gap-2" dir="ltr">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="glass-panel-strong pointer-events-auto flex items-start gap-3 rounded-xl px-4 py-3 animate-fade-in-up"
          >
            {iconMap[t.kind]}
            <p className="flex-1 text-sm text-foreground">{t.message}</p>
            <button onClick={() => dismiss(t.id)} className="text-muted-foreground hover:text-foreground">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

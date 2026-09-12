import { AlertTriangle } from 'lucide-react'
import Modal from './Modal'
import Button from './Button'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Standard confirmation modal for destructive/irreversible node & tunnel actions. */
const ConfirmDialog = ({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = true,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) => {
  return (
    <Modal open={open} onClose={onCancel} size="sm">
      <div className="flex flex-col items-center text-center gap-4 py-2">
        <div className={`flex h-12 w-12 items-center justify-center rounded-full ${danger ? 'bg-destructive/15 text-destructive' : 'bg-warning/15 text-warning'}`}>
          <AlertTriangle size={22} />
        </div>
        <div>
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex w-full gap-3 pt-2">
          <Button variant="secondary" className="flex-1" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} className="flex-1" onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default ConfirmDialog

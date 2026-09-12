import { InputHTMLAttributes, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

interface SecretFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  hint?: string
}

/**
 * Password / private-key input with a show-hide toggle.
 * Value is only ever kept in component state — never persisted to
 * localStorage or written to console — per the panel's security UX rules.
 */
const SecretField = ({ label, hint, id, className = '', ...rest }: SecretFieldProps) => {
  const [visible, setVisible] = useState(false)
  return (
    <div>
      {label && (
        <label htmlFor={id} className="field-label">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          className={`field-input pe-11 ${className}`}
          autoComplete="off"
          spellCheck={false}
          {...rest}
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setVisible((v) => !v)}
          className="absolute inset-y-0 end-2 flex items-center px-1.5 text-muted-foreground hover:text-foreground"
          aria-label={visible ? 'Hide secret' : 'Show secret'}
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}

export default SecretField

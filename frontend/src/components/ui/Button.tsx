import { ButtonHTMLAttributes, forwardRef } from 'react'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
  icon?: React.ReactNode
}

const variantClass: Record<Variant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', loading = false, icon, children, className = '', disabled, ...rest }, ref) => {
    return (
      <button
        ref={ref}
        className={`${variantClass[variant]} ${className}`}
        disabled={disabled || loading}
        {...rest}
      >
        {loading ? <Loader2 size={16} className="animate-spin" /> : icon}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'

export default Button

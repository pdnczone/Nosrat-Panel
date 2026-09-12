import { ReactNode } from 'react'

type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'brand'

const toneClass: Record<Tone, string> = {
  neutral: 'badge-neutral',
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  brand: 'badge-brand',
}

const Badge = ({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) => {
  return <span className={toneClass[tone]}>{children}</span>
}

export default Badge

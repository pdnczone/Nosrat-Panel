import { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  hover?: boolean
  strong?: boolean
}

/** Base glass surface used across the panel for cards, panels and sections. */
const Card = ({ children, hover = false, strong = false, className = '', ...rest }: CardProps) => {
  return (
    <div
      className={`${strong ? 'glass-panel-strong' : 'glass-panel'} rounded-2xl transition-all duration-250 ${
        hover ? 'hover:-translate-y-0.5 hover:shadow-glow-brand' : ''
      } ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}

export default Card

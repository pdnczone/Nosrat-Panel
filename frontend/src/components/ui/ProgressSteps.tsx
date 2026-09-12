import { Check } from 'lucide-react'

interface ProgressStepsProps {
  steps: string[]
  currentIndex: number
}

/** Horizontal numbered step indicator for multi-step flows (e.g. Add Node wizard). */
const ProgressSteps = ({ steps, currentIndex }: ProgressStepsProps) => {
  return (
    <div className="flex w-full items-center" dir="ltr">
      {steps.map((step, i) => {
        const done = i < currentIndex
        const active = i === currentIndex
        return (
          <div key={step} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-all duration-250 ${
                  done
                    ? 'brand-gradient-bg text-white'
                    : active
                    ? 'ring-2 ring-offset-2 ring-offset-background text-foreground'
                    : 'bg-secondary text-muted-foreground'
                }`}
                style={active ? { ['--tw-ring-color' as any]: 'hsl(var(--ring))' } : undefined}
              >
                {done ? <Check size={15} /> : i + 1}
              </div>
              <span className={`hidden text-[11px] sm:block ${active ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                {step}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`mx-2 h-0.5 flex-1 rounded-full transition-colors duration-250 ${done ? 'brand-gradient-bg' : 'bg-border'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export default ProgressSteps

interface Tab {
  id: string
  label: string
  icon?: React.ReactNode
}

interface TabsProps {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
}

const Tabs = ({ tabs, active, onChange }: TabsProps) => {
  return (
    <div role="tablist" className="inline-flex items-center gap-1 rounded-xl bg-secondary/50 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={active === tab.id}
          onClick={() => onChange(tab.id)}
          className={active === tab.id ? 'tab-pill-active flex items-center gap-1.5' : 'tab-pill flex items-center gap-1.5'}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export default Tabs

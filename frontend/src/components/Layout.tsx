import { ReactNode, useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Network, FileText, Activity, Moon, Sun, Menu, X, LogOut, Settings, Heart, Globe, Languages, Waypoints } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useLanguage } from '../contexts/LanguageContext'

interface LayoutProps {
  children: ReactNode
}

const NosratMark = ({ className = 'h-9 w-9' }: { className?: string }) => (
  <div className={`brand-mark ${className}`}>
    <Waypoints size={20} strokeWidth={2.25} />
  </div>
)

const Layout = ({ children }: LayoutProps) => {
  const location = useLocation()
  const navigate = useNavigate()
  const { logout, username } = useAuth()
  const { language, setLanguage, t } = useLanguage()
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : true
  })
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [version, setVersion] = useState('v0.1.0')

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  useEffect(() => {
    fetch('/api/status/version')
      .then((res) => res.json())
      .then((data) => {
        if (data.version) setVersion(`v${data.version}`)
      })
      .catch(() => setVersion('v0.1.0'))
  }, [])

  const navItems = [
    { path: '/dashboard', label: t.navigation.dashboard, icon: LayoutDashboard },
    { path: '/nodes', label: t.navigation.nodes, icon: Network },
    { path: '/servers', label: t.navigation.servers, icon: Globe },
    { path: '/tunnels', label: t.navigation.tunnels, icon: Activity },
    { path: '/core-health', label: t.navigation.coreHealth, icon: Heart },
    { path: '/logs', label: t.navigation.logs, icon: FileText },
    { path: '/settings', label: t.navigation.settings, icon: Settings },
  ]

  return (
    <div className="min-h-screen" dir="ltr">
      <div className="flex h-screen">
        {sidebarOpen && (
          <div className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm lg:hidden" onClick={() => setSidebarOpen(false)} />
        )}

        <aside
          dir="ltr"
          className={`fixed lg:static inset-y-0 left-0 z-50 flex w-72 flex-col glass-panel-strong border-e transition-transform duration-300 ease-in-out lg:translate-x-0 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <div className="flex items-center justify-between px-6 pt-6 lg:hidden">
            <span />
            <button onClick={() => setSidebarOpen(false)} className="btn-icon">
              <X size={20} />
            </button>
          </div>

          <div className="flex flex-col items-center gap-3 px-6 pb-6 pt-6 lg:pt-8">
            <NosratMark className="h-16 w-16" />
            <div className="text-center">
              <h1 className="text-xl font-bold brand-gradient-text">Nosrat</h1>
              <p className="text-xs text-muted-foreground">Tunnel &amp; Node Platform</p>
              {username && (
                <p className="mt-2 rounded-full bg-secondary/70 px-2.5 py-1 text-xs text-muted-foreground">{username}</p>
              )}
            </div>
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 rounded-xl px-4 py-2.5 text-sm transition-all duration-200 ${
                    isActive
                      ? 'brand-gradient-bg text-white shadow-glow-brand'
                      : 'text-foreground/80 hover:bg-secondary/60'
                  }`}
                >
                  <Icon size={18} />
                  <span className="font-medium">{item.label}</span>
                </Link>
              )
            })}
          </nav>

          <div className="space-y-2 border-t border-border/60 px-4 py-4">
            <div className="flex items-center justify-between px-1">
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {darkMode ? <Sun size={16} /> : <Moon size={16} />}
                {darkMode ? t.navigation.light : t.navigation.dark}
              </button>
              <button
                onClick={() => setLanguage(language === 'en' ? 'fa' : 'en')}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                title={language === 'en' ? 'Switch to Farsi' : 'Switch to English'}
              >
                <Languages size={16} />
                {language === 'en' ? 'EN' : 'FA'}
              </button>
            </div>
            <button
              onClick={() => { logout(); navigate('/login') }}
              className="flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
            >
              <LogOut size={16} />
              {t.navigation.logout}
            </button>
            <div className="flex items-center justify-center gap-1.5 pt-2 text-xs text-muted-foreground">
              <span>Nosrat {version}</span>
              <Heart size={11} className="text-destructive" />
            </div>
          </div>
        </aside>

        <main className="flex-1 overflow-auto" dir="ltr">
          <div className="sticky top-0 z-30 flex items-center justify-between glass-panel border-x-0 border-t-0 px-4 py-3 lg:hidden">
            <button onClick={() => setSidebarOpen(true)} className="btn-icon">
              <Menu size={22} />
            </button>
            <div className="flex items-center gap-2">
              <NosratMark className="h-7 w-7" />
              <span className="text-base font-bold brand-gradient-text">Nosrat</span>
            </div>
            <div className="w-9" />
          </div>

          <div className="p-4 sm:p-6 lg:p-8">{children}</div>
        </main>
      </div>
    </div>
  )
}

export default Layout

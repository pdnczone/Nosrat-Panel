import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogIn, Loader2, Waypoints, Moon, Sun } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useLanguage } from '../contexts/LanguageContext'
import api from '../api/client'

const Login = () => {
  const [username, setUsername] = useState('')
  const [version, setVersion] = useState('v0.1.0')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : true
  })
  const navigate = useNavigate()
  const { login, isAuthenticated } = useAuth()
  const { t, dir } = useLanguage()

  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard')
  }, [isAuthenticated, navigate])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  useEffect(() => {
    fetch('/api/status/version')
      .then((res) => res.json())
      .then((data) => {
        if (data.version) setVersion(`v${data.version}`)
      })
      .catch(() => setVersion('v0.1.0'))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const response = await api.post('/auth/login', { username, password })
      login(response.data.access_token, response.data.username)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || t.login.checkCredentials)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4" dir={dir}>
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mb-6 flex justify-center">
            <div className="brand-mark h-24 w-24">
              <Waypoints size={44} strokeWidth={2} />
            </div>
          </div>
          <h1 className="mb-2 text-4xl font-bold brand-gradient-text sm:text-5xl">Nosrat</h1>
          <p className="text-lg text-muted-foreground">Modern Tunnel &amp; Node Management Platform</p>
        </div>

        <div className="glass-panel-strong rounded-3xl p-8 sm:p-10 animate-fade-in-up">
          <div className="mb-8 flex items-center justify-between">
            <h2 className="text-2xl font-bold text-foreground">{t.login.signIn}</h2>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="btn-icon"
              title={darkMode ? 'Light mode' : 'Dark mode'}
            >
              {darkMode ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>

          {error && (
            <div className="mb-6 rounded-xl border border-destructive/30 bg-destructive/10 p-4">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="username" className="field-label">
                {t.login.username}
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="field-input"
                placeholder={t.login.usernamePlaceholder}
                autoComplete="username"
              />
            </div>

            <div>
              <label htmlFor="password" className="field-label">
                {t.login.password}
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="field-input"
                placeholder={t.login.passwordPlaceholder}
                autoComplete="current-password"
              />
            </div>

            <button type="submit" disabled={loading} className="btn-primary mt-2 w-full py-3.5 text-base">
              {loading ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  <span>{t.login.signingIn}</span>
                </>
              ) : (
                <>
                  <LogIn size={18} />
                  <span>{t.login.signIn}</span>
                </>
              )}
            </button>
          </form>
        </div>

        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>{version}</p>
        </div>
      </div>
    </div>
  )
}

export default Login

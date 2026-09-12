import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { LanguageProvider } from './contexts/LanguageContext'
import { ToastProvider } from './components/ui/Toast'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Nodes from './pages/Nodes'
import Servers from './pages/Servers'
import Tunnels from './pages/Tunnels'
import Logs from './pages/Logs'
import CoreHealth from './pages/CoreHealth'
import Settings from './pages/Settings'

// Protected Route Component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, checkAuth } = useAuth()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const verifyAuth = async () => {
      await checkAuth()
      setLoading(false)
    }
    verifyAuth()
  }, [checkAuth])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="brand-mark mx-auto mb-4 h-14 w-14 animate-pulse">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          </div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// App Routes Component
const AppRoutes = () => {
  const { isAuthenticated } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <Navigate to="/dashboard" replace />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/nodes"
        element={
          <ProtectedRoute>
            <Layout>
              <Nodes />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/servers"
        element={
          <ProtectedRoute>
            <Layout>
              <Servers />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/tunnels"
        element={
          <ProtectedRoute>
            <Layout>
              <Tunnels />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/logs"
        element={
          <ProtectedRoute>
            <Layout>
              <Logs />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/core-health"
        element={
          <ProtectedRoute>
            <Layout>
              <CoreHealth />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Layout>
              <Settings />
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

function App() {
  return (
    <Router>
      <LanguageProvider>
        <ToastProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </ToastProvider>
      </LanguageProvider>
    </Router>
  )
}

export default App


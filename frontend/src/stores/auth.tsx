import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { login, logout, register } from '../api/auth'

type Auth = {
  token: string | null
  name: string
  role: 'admin' | 'user'
  signIn: (identifier: string, password: string) => Promise<void>
  signUp: (email: string, name: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}
const AuthContext = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('modelgate-token'))
  const [name, setName] = useState(() => sessionStorage.getItem('modelgate-name') || 'Admin')
  const [role, setRole] = useState<'admin' | 'user'>(() => sessionStorage.getItem('modelgate-role') === 'user' ? 'user' : 'admin')
  const clearSession = useCallback(() => {
    sessionStorage.removeItem('modelgate-token')
    sessionStorage.removeItem('modelgate-name')
    sessionStorage.removeItem('modelgate-role')
    setToken(null)
    setName('Admin')
    setRole('admin')
  }, [])
  const acceptSession = useCallback((result: {token: string; name: string; role: 'admin' | 'user'}) => {
    sessionStorage.setItem('modelgate-token', result.token)
    sessionStorage.setItem('modelgate-name', result.name)
    sessionStorage.setItem('modelgate-role', result.role)
    setToken(result.token)
    setName(result.name)
    setRole(result.role)
  }, [])
  const signIn = useCallback(async (identifier: string, password: string) => {
    acceptSession(await login(identifier, password))
  }, [acceptSession])
  const signUp = useCallback(async (email: string, name: string, password: string) => {
    acceptSession(await register(email, name, password))
  }, [acceptSession])
  const signOut = useCallback(async () => {
    if (token) {
      try { await logout() } catch { /* Clear the local session even when the API is unavailable. */ }
    }
    clearSession()
  }, [clearSession, token])
  useEffect(() => {
    window.addEventListener('modelgate:unauthorized', clearSession)
    return () => window.removeEventListener('modelgate:unauthorized', clearSession)
  }, [clearSession])
  return <AuthContext.Provider value={{token, name, role, signIn, signUp, signOut}}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider is missing')
  return value
}

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { login } from '../api/auth'

type Auth = {
  token: string | null
  name: string
  signIn: (password: string) => Promise<void>
  signOut: () => void
}
const AuthContext = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('modelgate-token'))
  const [name, setName] = useState(() => sessionStorage.getItem('modelgate-name') || 'Demo Admin')
  const signOut = useCallback(() => {
    sessionStorage.removeItem('modelgate-token')
    sessionStorage.removeItem('modelgate-name')
    setToken(null)
    setName('Demo Admin')
  }, [])
  const signIn = useCallback(async (password: string) => {
    const result = await login(password)
    sessionStorage.setItem('modelgate-token', result.token)
    sessionStorage.setItem('modelgate-name', result.name)
    setToken(result.token)
    setName(result.name)
  }, [])
  useEffect(() => {
    window.addEventListener('modelgate:unauthorized', signOut)
    return () => window.removeEventListener('modelgate:unauthorized', signOut)
  }, [signOut])
  return <AuthContext.Provider value={{token, name, signIn, signOut}}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider is missing')
  return value
}

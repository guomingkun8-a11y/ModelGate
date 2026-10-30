import { http } from './http'
export type AuthSession = { token: string; name: string; role: 'admin' | 'user' }

export async function login(identifier: string, password: string) {
  return (await http.post<AuthSession>('/auth/login', { identifier, password })).data
}

export async function register(email: string, name: string, password: string) {
  return (await http.post<AuthSession>('/auth/register', { email, name, password })).data
}

export async function logout() {
  await http.post('/auth/logout')
}

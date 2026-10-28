import { http } from './http'
export async function login(password:string) { return (await http.post<{token:string;name:string}>('/auth/login', { password })).data }

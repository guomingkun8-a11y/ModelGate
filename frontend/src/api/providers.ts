import { http } from './http'
import type { Provider } from '../types'
export async function getProviders() { return (await http.get<Provider[]>('/providers')).data }
export async function updateProvider(id:string, patch:{enabled:boolean}) { return (await http.patch<Provider>(`/providers/${id}`,patch)).data }

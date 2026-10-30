import { http } from './http'
import type { Provider, ProviderModel, ProviderRecord } from '../types'
export interface ProviderInput { name:string; base_url:string; api_key?:string; models:ProviderModel[]; priority:number; weight:number }
export interface ProviderTestInput { provider_id?:string; base_url?:string; api_key?:string }
export async function createProvider(input:ProviderInput) { return (await http.post<Provider>('/providers',input)).data }
export async function getProviders() { return (await http.get<ProviderRecord[]>('/providers')).data }
export async function updateProvider(id:string, patch:Partial<ProviderInput> & {enabled?:boolean}) { return (await http.patch<Provider>(`/providers/${id}`,patch)).data }
export async function deleteProvider(id:string) { return (await http.delete<{ok:boolean}>(`/providers/${id}`)).data }
export async function publishProvider(id:string) { return (await http.post<Provider>(`/providers/${id}/publish`)).data }
export async function testProvider(input:ProviderTestInput) { return (await http.post<{ok:boolean;models:string[]}>('/providers/test',input)).data }

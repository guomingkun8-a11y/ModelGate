import { http } from './http'
import type { VirtualKey } from '../types'
export async function getVirtualKeys() { return (await http.get<VirtualKey[]>('/virtual-keys')).data }
export async function createVirtualKey(name:string,rpm_limit:number) { return (await http.post<{key:string;record:VirtualKey}>('/virtual-keys',{name,rpm_limit})).data }
export async function revokeVirtualKey(id:string) { await http.delete(`/virtual-keys/${id}`) }

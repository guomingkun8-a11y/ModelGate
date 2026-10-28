import { http } from './http'
export async function getSettings() { return (await http.get<Record<string,unknown>>('/settings')).data }

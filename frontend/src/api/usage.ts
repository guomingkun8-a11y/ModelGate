import { http } from './http'
import type { UsageData } from '../types'
export async function getUsage(hours=24) { return (await http.get<UsageData>('/usage',{params:{hours}})).data }

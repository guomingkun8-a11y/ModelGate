import { http } from './http'
import type { RequestRecord, PageResult, OverviewData } from '../types'
export async function getRequests(params:Record<string,string|number|undefined>={}) { return (await http.get<PageResult<RequestRecord>>('/requests',{params})).data }
export async function getRequest(id:string) { return (await http.get<RequestRecord>(`/requests/${id}`)).data }
export async function getOverview(hours=24) { return (await http.get<OverviewData>('/metrics/overview',{params:{hours}})).data }

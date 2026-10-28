import { http } from './http'
import type { ModelRoute } from '../types'
export async function getModelRoutes() { return (await http.get<ModelRoute[]>('/model-routes')).data }

import { http } from './http'
import type { Provider } from '../types'

export type PlaygroundMessage = { role: 'system' | 'user' | 'assistant'; content: string }
export type PlaygroundReply = {
  content: string
  latency_ms: number
  input_tokens: number | null
  output_tokens: number | null
  provider_id: string
  model: string
}

export async function getPlaygroundProviders() {
  return (await http.get<Provider[]>('/playground/providers')).data
}

export type PlaygroundRequestOptions = {
  temperature: number
  max_tokens: number
  signal?: AbortSignal
}

export async function sendPlaygroundMessage(provider_id: string, model: string, messages: PlaygroundMessage[], options: PlaygroundRequestOptions) {
  return (await http.post<PlaygroundReply>('/playground/chat', {
    provider_id, model, messages, temperature: options.temperature, max_tokens: options.max_tokens,
  }, { timeout: 120000, signal: options.signal })).data
}

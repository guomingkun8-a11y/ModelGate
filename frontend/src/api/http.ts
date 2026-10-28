import axios from 'axios'
export const http = axios.create({ baseURL: '/internal', timeout: 30000 })
http.interceptors.request.use(config => { const token = sessionStorage.getItem('modelgate-token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
http.interceptors.response.use(response => response, error => { if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) { sessionStorage.removeItem('modelgate-token'); window.dispatchEvent(new Event('modelgate:unauthorized')) } return Promise.reject(error) })
export function errorMessage(error: unknown):string { if (axios.isAxiosError(error)) { const data = error.response?.data; const message = data?.error?.message ?? data?.detail; if (typeof message === 'string') return message; return error.response ? '操作未完成，请稍后重试。' : '暂时无法连接网关，请确认后端已启动。' } return error instanceof Error ? error.message : '发生未知错误，请重试。' }

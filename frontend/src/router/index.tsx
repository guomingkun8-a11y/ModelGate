import { lazy, Suspense, useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Skeleton } from 'antd'
import AdminLayout from '../layouts/AdminLayout'
import { useAuth } from '../stores/auth'

const Login = lazy(() => import('../pages/Login'))
const Overview = lazy(() => import('../pages/Overview'))
const Providers = lazy(() => import('../pages/Providers'))
const ModelRoutes = lazy(() => import('../pages/ModelRoutes'))
const VirtualKeys = lazy(() => import('../pages/VirtualKeys'))
const RequestLogs = lazy(() => import('../pages/RequestLogs'))
const Usage = lazy(() => import('../pages/Usage'))
const Settings = lazy(() => import('../pages/Settings'))

export const pageTitles: Record<string, string> = {
  '/': '总览', '/providers': '供应商', '/model-routes': '模型路由', '/virtual-keys': '虚拟密钥',
  '/requests': '请求日志', '/usage': '用量统计', '/settings': '设置', '/login': '登录',
}

export default function AppRouter() {
  const { token } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: unknown } | null)?.from
  const afterLogin = typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') && !from.startsWith('/login') ? from : '/'
  useEffect(() => {
    document.title = `${pageTitles[location.pathname] || '控制台'} · ModelGate`
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [location.pathname])
  return <Suspense fallback={<div className="page-loading"><Skeleton active paragraph={{ rows: 8 }} /></div>}>
    <Routes>
      <Route path="/login" element={token ? <Navigate to={afterLogin} replace /> : <Login />} />
      <Route element={token ? <AdminLayout /> : <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />}>
        <Route index element={<Overview />} />
        <Route path="providers" element={<Providers />} />
        <Route path="model-routes" element={<ModelRoutes />} />
        <Route path="virtual-keys" element={<VirtualKeys />} />
        <Route path="requests" element={<RequestLogs />} />
        <Route path="usage" element={<Usage />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </Suspense>
}

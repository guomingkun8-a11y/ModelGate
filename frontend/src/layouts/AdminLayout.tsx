import { useState } from 'react'
import { Drawer } from 'antd'
import { Outlet } from 'react-router-dom'
import AppSidebar from '../components/AppSidebar'
import AppHeader from '../components/AppHeader'
import DemoRequestPanel from '../components/DemoRequestPanel'

export default function AdminLayout() {
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [testOpen, setTestOpen] = useState(false)
  return <div className="admin-shell"><a href="#main-content" className="skip-link">跳到主要内容</a><div className="desktop-sidebar"><AppSidebar /></div><Drawer open={navigationOpen} onClose={() => setNavigationOpen(false)} placement="left" width={244} styles={{body: {padding: 0}, header: {display: 'none'}}} title="导航"><AppSidebar onClose={() => setNavigationOpen(false)} /></Drawer><div className="main-shell"><AppHeader onMenu={() => setNavigationOpen(true)} onTest={() => setTestOpen(true)} /><main id="main-content" className="main-content"><Outlet /></main><footer className="app-footer"><span>ModelGate <span className="muted">/</span> 多模型统一网关</span><span>模拟供应商 · 本地数据 · 无外部 API 调用</span></footer></div><DemoRequestPanel open={testOpen} onClose={() => setTestOpen(false)} /></div>
}

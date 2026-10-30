import { useState } from 'react'
import { Drawer } from 'antd'
import { Outlet } from 'react-router-dom'
import AppSidebar from '../components/AppSidebar'
import AppHeader from '../components/AppHeader'

export default function AdminLayout() {
  const [navigationOpen, setNavigationOpen] = useState(false)
  return <div className="admin-shell"><a href="#main-content" className="skip-link">跳到主要内容</a><div className="desktop-sidebar"><AppSidebar /></div><Drawer open={navigationOpen} onClose={() => setNavigationOpen(false)} placement="left" width={244} styles={{body: {padding: 0}, header: {display: 'none'}}} title="导航"><AppSidebar onClose={() => setNavigationOpen(false)} /></Drawer><div className="main-shell"><AppHeader onMenu={() => setNavigationOpen(true)} /><main id="main-content" className="main-content"><Outlet /></main><footer className="app-footer"><span>ModelGate <span className="muted">/</span> 多模型统一网关</span><span>真实上游 · PostgreSQL 持久化</span></footer></div></div>
}

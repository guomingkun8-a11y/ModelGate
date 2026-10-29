import { NavLink } from 'react-router-dom'
import { Activity, ArrowUpRight, ChartNoAxesCombined, KeyRound, Layers3, LayoutDashboard, Network, Route, ScrollText, Settings } from 'lucide-react'
import { useAuth } from '../stores/auth'

const main = [{to: '/', label: '总览', icon: LayoutDashboard}, {to: '/providers', label: '供应商', icon: Network}, {to: '/model-routes', label: '模型路由', icon: Route}, {to: '/virtual-keys', label: '虚拟密钥', icon: KeyRound}]
const observe = [{to: '/requests', label: '请求日志', icon: ScrollText}, {to: '/usage', label: '用量统计', icon: ChartNoAxesCombined}]

export default function AppSidebar({onClose}: {onClose?: () => void}) {
  const {name} = useAuth()
  return <aside className="sidebar-content">
    <NavLink to="/" className="brand" onClick={onClose}><Layers3 size={29} strokeWidth={1.7} /><span>ModelGate<small>模型网关控制台</small></span></NavLink>
    <div className="workspace"><span className="workspace-avatar">M</span><div><strong>个人工作区</strong><small>本地演示环境</small></div><span className="status-dot" /></div>
    <nav aria-label="主导航"><p className="nav-section">工作空间</p>{main.map(({to, label, icon: Icon}) => <NavLink end={to === '/'} key={to} to={to} className={({isActive}) => `nav-item${isActive ? ' active' : ''}`} onClick={onClose}><Icon size={18} strokeWidth={1.7} /><span>{label}</span></NavLink>)}<p className="nav-section observe-label">可观测性</p>{observe.map(({to, label, icon: Icon}) => <NavLink key={to} to={to} className={({isActive}) => `nav-item${isActive ? ' active' : ''}`} onClick={onClose}><Icon size={18} strokeWidth={1.7} /><span>{label}</span></NavLink>)}<div className="nav-divider" /><NavLink to="/settings" className={({isActive}) => `nav-item${isActive ? ' active' : ''}`} onClick={onClose}><Settings size={18} strokeWidth={1.7} /><span>设置</span></NavLink></nav>
    <div className="sidebar-bottom"><div className="demo-note"><Activity size={17} /><strong>一个入口，多种可能</strong><p>统一模型调用，专注构建。</p><NavLink to="/settings" onClick={onClose}>查看环境信息<ArrowUpRight size={13} /></NavLink></div><div className="profile"><span className="profile-avatar">D</span><div><strong>{name}</strong><small>管理员</small></div><span className="profile-label">LOCAL</span></div></div>
  </aside>
}

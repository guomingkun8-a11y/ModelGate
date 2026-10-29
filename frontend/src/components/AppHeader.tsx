import { Button, Tooltip } from 'antd'
import { ChevronRight, LogOut, Menu, Play } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../stores/auth'

const titles: Record<string, string> = {'/': '总览', '/providers': '供应商', '/model-routes': '模型路由', '/virtual-keys': '虚拟密钥', '/requests': '请求日志', '/usage': '用量统计', '/settings': '设置'}
export default function AppHeader({onMenu, onTest}: {onMenu: () => void; onTest: () => void}) {
  const location = useLocation(), {signOut} = useAuth()
  return <header className="app-header"><div className="header-breadcrumb"><Button type="text" className="mobile-menu" aria-label="打开导航" icon={<Menu size={20} />} onClick={onMenu} /><span>工作空间</span><ChevronRight size={13} /><strong>{titles[location.pathname] || '控制台'}</strong></div><div className="header-actions"><span className="environment-badge"><span className="status-dot" />演示环境</span><Button icon={<Play size={14} />} onClick={onTest}>测试请求</Button><Tooltip title="退出登录"><Button type="text" aria-label="退出登录" icon={<LogOut size={17} />} onClick={signOut} /></Tooltip></div></header>
}

import { Button, Tooltip } from 'antd'
import { ChevronRight, LogOut, Menu } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../stores/auth'

const titles: Record<string, string> = {'/playground': '模型测试', '/console': '总览', '/providers': '供应商', '/model-routes': '模型路由', '/virtual-keys': '虚拟密钥', '/requests': '请求日志', '/usage': '用量统计', '/settings': '设置'}
export default function AppHeader({onMenu}: {onMenu: () => void}) {
  const location = useLocation(), {signOut, role} = useAuth()
  const title = role === 'user' && location.pathname === '/providers' ? '可用渠道' : role === 'user' && location.pathname === '/model-routes' ? '可用模型' : titles[location.pathname] || '控制台'
  return <header className="app-header"><div className="header-breadcrumb"><Button type="text" className="mobile-menu" aria-label="打开导航" icon={<Menu size={20} />} onClick={onMenu} /><span>工作空间</span><ChevronRight size={13} /><strong>{title}</strong></div><div className="header-actions"><Tooltip title="退出登录"><Button type="text" aria-label="退出登录" icon={<LogOut size={17} />} onClick={signOut} /></Tooltip></div></header>
}

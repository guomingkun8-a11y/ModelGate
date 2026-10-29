import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { Button, Result } from 'antd'
import { BrowserRouter } from 'react-router-dom'
import AppRouter from './router'

class ErrorBoundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('页面载入失败', error, info.componentStack) }
  render() {
    if (this.state.failed) return <Result status="warning" title="页面暂时无法打开" subTitle="可能是应用刚刚更新，请刷新后重试。" extra={<Button type="primary" onClick={() => window.location.reload()}>刷新页面</Button>} />
    return this.props.children
  }
}

export default function App() {
  return <ErrorBoundary><BrowserRouter><AppRouter /></BrowserRouter></ErrorBoundary>
}

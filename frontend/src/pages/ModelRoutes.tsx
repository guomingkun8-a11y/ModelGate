import { Alert, Button, Empty, Skeleton } from 'antd'
import { ArrowRight, GitBranch, RefreshCw, Server } from 'lucide-react'
import { getModelRoutes } from '../api/modelRoutes'
import { getProviders } from '../api/providers'
import StatusTag from '../components/StatusTag'
import { useData } from '../hooks/useData'
import type { Provider } from '../types'

export default function ModelRoutes() {
  const { data, loading, error, refresh } = useData(async () => {
    const [routes, providers] = await Promise.all([getModelRoutes(), getProviders()])
    return { routes, providers }
  })
  return <>
    <section className="page-heading"><div><h1 className="page-title">模型路由</h1><p className="page-subtitle">一个模型入口，连接多个供应商。按优先级分配，失败时自动切换。</p></div><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新路由</Button></section>
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    {loading && !data ? <Skeleton active paragraph={{ rows: 8 }} /> : data && <>
      <div className="route-label"><span>{data.routes.length} 条模型路由</span><span className="muted">只读配置 · 通过演示请求验证选路</span></div>
      {data.routes.map(route => {
        const providers = route.provider_ids.map(id => data.providers.find(provider => provider.id === id)).filter((provider): provider is Provider => Boolean(provider)).sort((a, b) => b.priority - a.priority)
        return <section className="panel route-panel" key={route.id}>
          <div className="panel-head"><div className="route-heading"><GitBranch size={18} /><h2 className="panel-title">{route.name || route.model}</h2><span className="model-name">{route.model}</span></div><StatusTag status={route.enabled ? 'active' : 'disabled'} /></div>
          <div className="route-body"><div className="route-entry"><span className="muted">公开模型名</span><strong className="mono">{route.model}</strong><span className="plain-tag">OpenAI 兼容接口</span></div><div className="route-connector"><span className="route-line" /><ArrowRight size={18} /><span className="route-line" /></div>
            <div className="route-targets">{providers.map(provider => <div className="route-target" key={provider.id}><span className="provider-avatar"><Server size={17} /></span><div className="route-target-name"><strong>{provider.name}</strong><span className="muted">优先级 {provider.priority} · 权重 {provider.weight}</span></div><StatusTag status={provider.enabled ? provider.status : 'disabled'} /></div>)}{!providers.length && <Empty description="此路由暂无上游。" />}</div>
          </div>
          <div className="route-footer"><span>路由策略 <strong>优先级 + 权重</strong></span><span>最多尝试 <strong>3 个不同上游</strong></span><span>SSE 开始后不再切换</span></div>
        </section>
      })}
      {!data.routes.length && <Empty description="没有模型路由，请先初始化演示配置。" />}
    </>}
  </>
}

import { Alert, Button, Empty, Skeleton } from 'antd'
import { ArrowRight, GitBranch, RefreshCw, Server } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getModelRoutes } from '../api/modelRoutes'
import { getProviders } from '../api/providers'
import StatusTag from '../components/StatusTag'
import { useData } from '../hooks/useData'
import { useAuth } from '../stores/auth'
import type { Provider, ProviderRecord } from '../types'

function isManagedProvider(provider: ProviderRecord): provider is Provider {
  return 'priority' in provider
}

export default function ModelRoutes() {
  const { role } = useAuth()
  const { data, loading, error, refresh } = useData(async () => {
    const [routes, providers] = await Promise.all([getModelRoutes(), getProviders()])
    return { routes, providers }
  })
  return <>
    <section className="page-heading"><div><h1 className="page-title">{role === 'admin' ? '模型路由' : '可用模型'}</h1><p className="page-subtitle">{role === 'admin' ? '查看公开模型对应的渠道和自动切换策略。' : '通过虚拟密钥调用公开模型，请求会由平台自动分配到可用渠道。'}</p></div><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新</Button></section>
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    {loading && !data ? <Skeleton active paragraph={{ rows: 8 }} /> : data && <>
      <div className="route-label"><span>{data.routes.length} 个{role === 'admin' ? '模型路由' : '可用模型'}</span><span className="muted">{role === 'admin' ? '由已配置渠道自动生成' : '由管理员配置并发布'}</span></div>
      {data.routes.map(route => {
        const providers = route.provider_ids.map(id => data.providers.find(provider => provider.id === id)).filter((provider): provider is ProviderRecord => Boolean(provider)).sort((a, b) => role === 'admin' ? (isManagedProvider(b) ? b.priority : 0) - (isManagedProvider(a) ? a.priority : 0) : 0)
        return <section className="panel route-panel" key={route.id}>
          <div className="panel-head"><div className="route-heading"><GitBranch size={18} /><h2 className="panel-title">{route.name || route.model}</h2><span className="model-name">{route.model}</span></div><StatusTag status={route.enabled ? 'active' : 'disabled'} /></div>
          <div className="route-body"><div className="route-entry"><span className="muted">公开模型名</span><strong className="mono">{route.model}</strong><span className="plain-tag">OpenAI 兼容接口</span></div><div className="route-connector"><span className="route-line" /><ArrowRight size={18} /><span className="route-line" /></div>
            <div className="route-targets">{providers.map(provider => { const managed = isManagedProvider(provider); return <div className="route-target" key={provider.id}><span className="provider-avatar"><Server size={17} /></span><div className="route-target-name"><strong>{provider.name}</strong><span className="muted">{role === 'admin' && managed ? `上游模型 ${provider.models.find(model => model.public_model === route.model)?.upstream_model ?? '未配置'} · 优先级 ${provider.priority} · 权重 ${provider.weight}` : provider.kind}</span></div><StatusTag status={provider.enabled ? provider.status : 'disabled'} /></div> })}{!providers.length && <Empty description={role === 'admin' ? '此路由暂无配置渠道。' : '此模型当前没有可用渠道。'} />}</div>
          </div>
          {role === 'admin' && <div className="route-footer"><span>路由策略 <strong>优先级 + 权重</strong></span><span>最多尝试 <strong>3 个不同上游</strong></span><span>SSE 开始后不再切换</span></div>}
        </section>
      })}
      {!data.routes.length && <Empty description={role === 'admin' ? <span>还没有模型路由。<Link to="/providers">添加渠道</Link> 后，路由会自动生成。</span> : '管理员尚未发布可用模型。'} />}
    </>}
  </>
}

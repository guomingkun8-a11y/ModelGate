import { useState } from 'react'
import { Alert, App, Button, Empty, Skeleton, Switch, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ArrowUpRight, RefreshCw, Server } from 'lucide-react'
import { getProviders, updateProvider } from '../api/providers'
import { errorMessage } from '../api/http'
import StatusTag from '../components/StatusTag'
import { useData } from '../hooks/useData'
import type { Provider } from '../types'

export default function Providers() {
  const { message } = App.useApp()
  const { data, loading, error, refresh } = useData(getProviders)
  const [updating, setUpdating] = useState<string[]>([])

  async function toggle(provider: Provider, enabled: boolean) {
    if (updating.includes(provider.id)) return
    setUpdating(value => [...value, provider.id])
    try {
      await updateProvider(provider.id, { enabled })
      window.dispatchEvent(new Event('modelgate:refresh'))
      message.success(`${provider.name} 已${enabled ? '启用' : '停用'}`)
    } catch (reason) {
      message.error(errorMessage(reason))
    } finally {
      setUpdating(value => value.filter(id => id !== provider.id))
    }
  }

  const columns: ColumnsType<Provider> = [
    { title: '供应商', dataIndex: 'name', width: 215, render: (_, row) => <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}><span className="provider-avatar"><Server size={17} /></span><div><strong>{row.name}</strong><small className="table-secondary">{row.kind}</small></div></div> },
    { title: '支持模型', dataIndex: 'models', width: 240, render: (models: string[]) => <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>{models.map(model => <span className="model-name" key={model}>{model}</span>)}</div> },
    { title: '状态', render: (_, row) => <StatusTag status={row.enabled ? row.status : 'disabled'} /> },
    { title: '模拟延迟', render: (_, row) => <span className="mono">{row.latency_ms.toLocaleString()} <span className="muted">ms</span></span> },
    { title: '成功率', render: (_, row) => <span className="mono">{row.success_rate.toFixed(1)}%</span> },
    { title: '优先级 / 权重', render: (_, row) => <span className="mono">{row.priority} <span className="muted">/ {row.weight}</span></span> },
    { title: '启用', fixed: 'right', width: 80, render: (_, row) => <Switch checked={row.enabled} loading={updating.includes(row.id)} disabled={loading || updating.includes(row.id)} aria-label={`${row.enabled ? '停用' : '启用'} ${row.name}`} onChange={enabled => toggle(row, enabled)} /> },
  ]

  return <>
    <section className="page-heading"><div><h1 className="page-title">供应商</h1><p className="page-subtitle">管理模型上游，观察每一条调用通道的可用状态。</p></div><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新状态</Button></section>
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    {loading && !data ? <Skeleton active paragraph={{ rows: 7 }} /> : data && <>
      <div className="note-banner"><Server size={16} /><span><strong>{data.filter(provider => provider.enabled).length} / {data.length} 已启用</strong> · 此环境的所有上游均为本地模拟，不访问外部服务。</span></div>
      <section className="panel"><div className="panel-head"><h2 className="panel-title">上游连接</h2><span className="muted">状态变更即时生效</span></div><Table<Provider> rowKey="id" columns={columns} dataSource={data} pagination={false} scroll={{ x: 1040 }} size="middle" locale={{ emptyText: <Empty description="尚未配置供应商，请初始化演示上游。" /> }} /></section>
      <div className="note-banner section-gap"><ArrowUpRight size={18} /><div><strong>试试关闭主通道</strong><p style={{ margin: '6px 0 0' }}>停用高优先级上游后，再发起测试请求，在日志中查看新的路由结果。关闭全部通道时，请求会明确返回不可用。</p></div></div>
    </>}
  </>
}

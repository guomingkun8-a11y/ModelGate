import { useEffect, useState } from 'react'
import { Alert, Button, Empty, Select, Skeleton, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, CheckCheck, RefreshCw, Timer, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getOverview } from '../api/requests'
import StatCard from '../components/StatCard'
import StatusTag from '../components/StatusTag'
import TrendChart from '../components/TrendChart'
import { useData } from '../hooks/useData'
import type { RequestRecord } from '../types'

const number = (value: number) => new Intl.NumberFormat('zh-CN').format(value)
const time = (value: string) => new Date(value).toLocaleTimeString('zh-CN', { hour12: false })

export default function Overview() {
  const [hours, setHours] = useState(24)
  const [updated, setUpdated] = useState('')
  const { data, loading, error, refresh } = useData(() => getOverview(hours), [hours])
  useEffect(() => { if (data) setUpdated(new Date().toLocaleTimeString('zh-CN', { hour12: false })) }, [data])

  function download() {
    if (!data) return
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'modelgate-overview.json'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const columns: ColumnsType<RequestRecord> = [
    { title: '请求 ID / 时间', dataIndex: 'id', render: (_, row) => <><Link className="request-id mono" to={`/requests?q=${encodeURIComponent(row.id)}`}>{row.id.slice(0, 21)}</Link><small className="table-secondary mono">{time(row.created_at)}</small></> },
    { title: '模型', dataIndex: 'model', render: value => <span className="model-name">{value}</span> },
    { title: '供应商', dataIndex: 'provider' },
    { title: '状态', dataIndex: 'status', render: value => <StatusTag status={value} /> },
    { title: '延迟', align: 'right', render: (_, row) => <span className="mono">{number(row.latency_ms)} <span className="muted">ms</span></span> },
    { title: 'Token', align: 'right', render: (_, row) => <span className="mono">{number((row.input_tokens ?? 0) + (row.output_tokens ?? 0))}</span> },
    { title: '模式', align: 'right', render: (_, row) => <span className="plain-tag">{row.is_stream ? 'SSE' : 'JSON'}</span> },
  ]

  return <>
    <section className="page-heading">
      <div><div className="title-line"><h1 className="page-title">网关总览</h1></div><p className="page-subtitle">流量、模型与运行状态，一目了然。</p></div>
      <div className="page-actions"><Select aria-label="统计时间范围" value={hours} onChange={setHours} style={{ width: 145 }} options={[{ value: 1, label: '最近 1 小时' }, { value: 24, label: '最近 24 小时' }, { value: 168, label: '最近 7 天' }]} /><Button icon={<ArrowDownToLine size={15} />} disabled={!data} onClick={download}>导出报告</Button></div>
    </section>
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    {loading && !data ? <Skeleton active paragraph={{ rows: 12 }} /> : data && <>
      <div className="stats-grid">
        <StatCard label="总请求数" value={number(data.requests)} description="当前时间范围内的所有请求" icon={<Activity size={17} />} />
        <StatCard label="请求成功率" value={`${data.success_rate.toFixed(1)}%`} description="成功完成的请求占比" icon={<CheckCheck size={18} />} />
        <StatCard label="P95 响应延迟" value={number(Math.round(data.p95_latency_ms))} unit="ms" description="95% 的请求在此时间内完成" icon={<Timer size={17} />} />
        <StatCard label="Token 用量" value={data.tokens >= 1000 ? `${(data.tokens / 1000).toFixed(1)}k` : number(data.tokens)} description="输入与输出合计" icon={<Zap size={17} />} />
      </div>
      <div className="overview-middle">
        <section className="panel traffic-panel"><div className="panel-head"><div><h2 className="panel-title">请求流量</h2><p className="panel-description">当前时间范围内的请求分布</p></div><div className="chart-legend"><span className="legend-line" />请求量</div></div><div className="chart-body"><TrendChart series={data.series} /></div></section>
        <section className="panel upstream-panel"><div className="panel-head"><h2 className="panel-title">上游状态</h2><Link className="icon-btn" aria-label="查看供应商" to="/providers"><ArrowUpRight size={17} /></Link></div>
          <div className="upstream-list">{data.providers.map((provider, index) => <div className="upstream-row" key={provider.id}><span className={`provider-avatar provider-color-${index % 3}`}>{provider.name.slice(0, 1).toUpperCase()}</span><div className="upstream-name"><strong>{provider.name}</strong><span>{provider.kind}</span></div><div className="upstream-health"><StatusTag status={provider.enabled ? provider.status : 'disabled'} /></div></div>)}</div>
          <div className="upstream-summary"><span className={`status-dot ${!data.providers.some(p => p.enabled) ? 'disabled-dot' : ''}`} />{data.providers.filter(p => p.enabled).length} / {data.providers.length} 个上游已启用<Link className="text-link" to="/model-routes">查看路由<ArrowRight size={13} /></Link></div>
        </section>
      </div>
      <section className="panel recent-panel"><div className="panel-head"><div className="panel-title-with-count"><h2 className="panel-title">最近请求</h2><span className="count-badge">{data.recent_requests.slice(0, 5).length}</span></div><Link className="text-link" to="/requests">查看全部<ArrowRight size={14} /></Link></div><Table<RequestRecord> rowKey="id" columns={columns} dataSource={data.recent_requests.slice(0, 5)} pagination={false} size="middle" scroll={{ x: 840 }} locale={{ emptyText: <Empty description="还没有请求记录。" /> }} /></section>
      <div className="overview-meta"><span><span className={`status-dot ${error ? 'disabled-dot' : ''}`} />{error ? '连接失败，显示上次数据' : '网关已连接'}</span><span>数据更新于 {updated}<Button type="text" size="small" loading={loading} icon={<RefreshCw size={13} />} aria-label="刷新数据" onClick={refresh} /></span></div>
    </>}
  </>
}

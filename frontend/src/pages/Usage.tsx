import { useState } from 'react'
import { Alert, Button, Empty, Progress, Select, Skeleton, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Info, RefreshCw } from 'lucide-react'
import { getUsage } from '../api/usage'
import StatCard from '../components/StatCard'
import TrendChart from '../components/TrendChart'
import { useData } from '../hooks/useData'
import type { ModelUsage } from '../types'

const number = (value: number) => Intl.NumberFormat('zh-CN').format(value)

export default function Usage() {
  const [hours, setHours] = useState(24)
  const { data, loading, error, refresh } = useData(() => getUsage(hours), [hours])
  const models = [...(data?.by_model ?? [])].sort((a, b) => b.tokens - a.tokens)
  const columns: ColumnsType<ModelUsage> = [
    { title: '模型', dataIndex: 'model', render: value => <strong className="mono">{value}</strong> },
    { title: '请求次数', dataIndex: 'requests', render: value => <span className="mono">{number(value)}</span> },
    { title: 'Token 用量', dataIndex: 'tokens', render: value => <span className="mono">{number(value)}</span> },
    { title: '用量占比', dataIndex: 'tokens', width: 250, render: value => <Progress percent={data?.total_tokens ? Number((value / data.total_tokens * 100).toFixed(1)) : 0} strokeColor="var(--primary)" size="small" /> },
  ]
  return <>
    <section className="page-heading"><div><h1 className="page-title">用量分析</h1><p className="page-subtitle">了解请求与 Token 的分布，为模型使用提供可追溯的数据。</p></div><div className="page-actions"><Select aria-label="用量时间范围" value={hours} onChange={setHours} style={{ width: 145 }} options={[{ value: 1, label: '最近 1 小时' }, { value: 24, label: '最近 24 小时' }, { value: 168, label: '最近 7 天' }]} /><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新</Button></div></section>
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    {loading && !data ? <Skeleton active paragraph={{ rows: 9 }} /> : data && <>
      <div className="stats-grid"><StatCard label="总请求数" value={number(data.total_requests)} description="所选时间范围内" /><StatCard label="输入 Token" value={number(data.input_tokens)} description="上游报告的输入用量" /><StatCard label="输出 Token" value={number(data.output_tokens)} description="上游报告的输出用量" /><StatCard label="总 Token" value={number(data.total_tokens)} description="输入与输出合计" /></div>
      <section className="panel section-gap"><div className="panel-head"><h2 className="panel-title">请求趋势</h2><span className="muted">所选时间范围内的请求分布</span></div><div className="panel-body"><TrendChart series={data.series} /></div></section>
      <section className="panel section-gap"><div className="panel-head"><h2 className="panel-title">按模型分布</h2><span className="muted">{models.length} 个模型</span></div><Table<ModelUsage> columns={columns} rowKey="model" dataSource={models} pagination={false} size="middle" scroll={{ x: 660 }} locale={{ emptyText: <Empty description="所选时间范围暂无调用记录。" /> }} /></section>
      <p className="field-note" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}><Info size={16} />Token 来自上游实际返回的用量报告，用于用量分析。</p>
    </>}
  </>
}

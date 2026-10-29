import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Descriptions, Drawer, Empty, Input, Select, Skeleton, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ArrowRight, RefreshCw, Search } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { errorMessage } from '../api/http'
import { getRequest, getRequests } from '../api/requests'
import StatusTag from '../components/StatusTag'
import { useData } from '../hooks/useData'
import type { RequestRecord } from '../types'

const time = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false })

export default function RequestLogs() {
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const [input, setInput] = useState(query)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [detail, setDetail] = useState<RequestRecord>()
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const detailVersion = useRef(0)
  const { data, loading, error, refresh } = useData(() => getRequests({ page, page_size: 10, q: query || undefined, status: status || undefined }), [page, query, status])

  useEffect(() => { setInput(query); setPage(1) }, [query])
  useEffect(() => {
    const version = ++detailVersion.current
    if (!detailId) return
    setDetail(undefined)
    setDetailLoading(true)
    setDetailError('')
    getRequest(detailId).then(record => { if (detailVersion.current === version) setDetail(record) }).catch(reason => { if (detailVersion.current === version) setDetailError(errorMessage(reason)) }).finally(() => { if (detailVersion.current === version) setDetailLoading(false) })
    return () => { detailVersion.current++ }
  }, [detailId])

  function search() {
    setPage(1)
    const next = new URLSearchParams(params)
    if (input.trim()) next.set('q', input.trim())
    else next.delete('q')
    if (query === input.trim() && page === 1) refresh()
    else setParams(next, { replace: true })
  }

  const columns: ColumnsType<RequestRecord> = [
    { title: '请求 ID / 时间', dataIndex: 'id', width: 230, render: (_, row) => <><Button className="request-id mono" type="link" onClick={() => setDetailId(row.id)}>{row.id.slice(0, 21)}</Button><small className="table-secondary mono">{time(row.created_at)}</small></> },
    { title: '模型', dataIndex: 'model', render: (_, row) => <><span className="model-name">{row.model}</span><small className="table-secondary">{row.is_stream ? 'SSE 流式' : 'JSON 响应'}</small></> },
    { title: '供应商', dataIndex: 'provider', render: value => value || '未分配' },
    { title: '状态', dataIndex: 'status', render: value => <StatusTag status={value} /> },
    { title: '耗时', align: 'right', render: (_, row) => <span className="mono">{row.latency_ms} <span className="muted">ms</span></span> },
    { title: 'Token', align: 'right', render: (_, row) => <span className="mono">{(row.input_tokens + row.output_tokens).toLocaleString('zh-CN')}</span> },
    { title: '尝试', align: 'right', render: (_, row) => row.attempts.length },
    { title: '', width: 50, render: (_, row) => <Button type="text" icon={<ArrowRight size={15} />} aria-label={`查看请求 ${row.id}`} onClick={() => setDetailId(row.id)} /> },
  ]
  return <>
    <section className="page-heading"><div><h1 className="page-title">请求日志</h1><p className="page-subtitle">查看每次模型调用，沿着尝试记录定位问题。</p></div><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新</Button></section>
    <section className="panel"><form className="table-toolbar" onSubmit={event => { event.preventDefault(); search() }}><Input aria-label="搜索请求" prefix={<Search size={16} />} placeholder="搜索请求 ID、模型或供应商…" value={input} onChange={event => setInput(event.target.value)} allowClear style={{ maxWidth: 340 }} /><Select aria-label="筛选请求状态" value={status} onChange={value => { setStatus(value); setPage(1) }} style={{ minWidth: 126 }} options={[{ value: '', label: '全部状态' }, { value: 'success', label: '成功' }, { value: 'error', label: '失败' }]} /><Button htmlType="submit">搜索</Button><span className="toolbar-count">{data?.total ?? 0} 条请求</span></form>
      {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} />}
      <Table<RequestRecord> rowKey="id" columns={columns} dataSource={data?.items ?? []} loading={loading} scroll={{ x: 980 }} size="middle" pagination={{ current: page, pageSize: 10, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false, showTotal: total => `共 ${total} 条` }} locale={{ emptyText: <Empty description="没有找到请求，调整搜索条件或发起一次测试。" /> }} />
    </section>
    <p className="field-note">日志仅记录元数据与模拟 Token，不保存提示词或完整响应正文。</p>
    <Drawer title="请求详情" open={Boolean(detailId)} onClose={() => setDetailId(null)} width={560}>
      {detailLoading ? <Skeleton active paragraph={{ rows: 9 }} /> : detailError ? <Alert type="error" showIcon message={detailError} /> : detail && <>
        <div className="detail-status"><StatusTag status={detail.status} /><Tag>演示请求</Tag></div>
        <h3 className="detail-section-title">请求信息</h3>
        <Descriptions column={1} size="small" items={[
          { key: 'id', label: '请求 ID', children: <span className="mono" style={{ overflowWrap: 'anywhere' }}>{detail.id}</span> },
          { key: 'model', label: '公开模型', children: detail.model },
          { key: 'time', label: '创建时间', children: time(detail.created_at) },
          { key: 'provider', label: '最终上游', children: detail.provider || '未分配' },
          { key: 'latency', label: '状态码 / 总延迟', children: `${detail.status_code} / ${detail.latency_ms} ms` },
          { key: 'tokens', label: '输入 / 输出 Token', children: `${detail.input_tokens} / ${detail.output_tokens}` },
        ]} />
        {detail.error && <Alert type="error" showIcon message={detail.error} style={{ marginTop: 16 }} />}
        <h3 className="detail-section-title">上游尝试 <span className="count-badge">{detail.attempts.length}</span></h3>
        {detail.attempts.map((attempt, index) => <div className="attempt-row" key={`${attempt.provider_id}-${index}`}><span className="attempt-number">{index + 1}</span><div><strong>{attempt.provider}</strong><span className="attempt-error">{attempt.error || '响应成功'}</span></div><span className={`mono ${attempt.status_code >= 400 ? 'danger-text' : 'success-text'}`}>{attempt.status_code}</span><span className="mono muted">{attempt.latency_ms} ms</span></div>)}
        {!detail.attempts.length && <Empty description="请求未进入上游执行阶段。" />}
      </>}
    </Drawer>
  </>
}

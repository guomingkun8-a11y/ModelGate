import { useEffect, useRef, useState } from 'react'
import { Alert, App, Button, Drawer, Form, Input, Select, Switch } from 'antd'
import { ArrowRight, CheckCircle2, Copy, Play, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getModelRoutes } from '../api/modelRoutes'
import { sendDemoRequest } from '../api/requests'
import { errorMessage } from '../api/http'
import type { ModelRoute, RequestRecord } from '../types'

export default function DemoRequestPanel({open, onClose}: {open: boolean; onClose: () => void}) {
  const {message} = App.useApp()
  const [routes, setRoutes] = useState<ModelRoute[]>([])
  const [model, setModel] = useState('')
  const [prompt, setPrompt] = useState('请用简洁的语言介绍一下 ModelGate 的作用。')
  const [simulateFailure, setSimulateFailure] = useState(false)
  const [loading, setLoading] = useState(false)
  const [modelsLoading, setModelsLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<{request: RequestRecord; answer: string} | null>(null)
  const pending = useRef(false)
  useEffect(() => {
    if (!open) return
    let current = true
    setError(''); setModelsLoading(true); setRoutes([])
    getModelRoutes().then(value => {
      if (!current) return
      const enabled = value.filter(route => route.enabled)
      setRoutes(enabled)
      setModel(previous => enabled.some(route => route.model === previous) ? previous : enabled[0]?.model || '')
    }).catch(reason => { if (current) setError(errorMessage(reason)) }).finally(() => {if (current) setModelsLoading(false)})
    return () => {current = false}
  }, [open])
  async function send() {
    if (pending.current || modelsLoading || !routes.some(route => route.model === model)) return
    if (!model || !prompt.trim()) {setError('请选择模型并输入测试内容。'); return}
    pending.current = true
    setLoading(true); setError(''); setResult(null)
    try {
      setResult(await sendDemoRequest({model, prompt: prompt.trim(), simulate_failure: simulateFailure, stream: false}))
      window.dispatchEvent(new Event('modelgate:refresh'))
    } catch (reason) {setError(errorMessage(reason))}
    finally {pending.current = false; setLoading(false)}
  }
  async function copy() {
    const body = JSON.stringify({model, messages: [{role: 'user', content: 'Hello'}]})
    try {
      await navigator.clipboard.writeText(`curl ${window.location.origin}/v1/chat/completions \\\n  -H "Authorization: Bearer sk-demo-local" \\\n  -H "Content-Type: application/json" \\\n  -d '${body}'`)
      void message.success('调用示例已复制')
    } catch {void message.error('复制失败，请检查浏览器剪贴板权限')}
  }
  return <Drawer title="测试模型请求" open={open} onClose={onClose} width={580} className="test-drawer" maskClosable={!loading} keyboard={!loading}>
    <div className="drawer-intro"><span className="environment-badge">受控模拟上游</span><p>发起一次请求，观察模型选路和故障切换。不会访问外部模型服务。</p></div>
    <Form layout="vertical" onFinish={() => void send()}>
      <Form.Item label="公开模型"><Select value={model || undefined} onChange={setModel} loading={modelsLoading} placeholder="请选择模型" aria-label="公开模型" options={routes.map(route => ({value: route.model, label: route.model}))} disabled={loading} /></Form.Item>
      <Form.Item label="测试内容" htmlFor="test-prompt"><Input.TextArea id="test-prompt" value={prompt} onChange={event => setPrompt(event.target.value)} rows={4} maxLength={2000} showCount placeholder="输入一条测试消息" disabled={loading} /></Form.Item>
      <div className="simulation-control"><div><strong>模拟首次上游失败</strong><p>首次尝试返回 503，观察备用上游接管。</p></div><Switch checked={simulateFailure} onChange={setSimulateFailure} aria-label="模拟首次上游失败" disabled={loading} /></div>
      {error && <Alert type="error" showIcon message={error} style={{marginBottom: 16}} />}
      <div className="test-actions"><Button type="primary" htmlType="submit" loading={loading} disabled={!model || modelsLoading || !routes.length} icon={<Play size={14} />}>发送测试请求</Button><Button type="text" icon={<Copy size={14} />} onClick={() => void copy()} disabled={!model || !routes.length}>复制 cURL</Button></div>
    </Form>
    {result && <section className="test-result"><div className={`result-header ${result.request.status === 'success' ? 'success-text' : 'danger-text'}`}>{result.request.status === 'success' ? <CheckCircle2 size={18} /> : <XCircle size={18} />}<strong>{result.request.status === 'success' ? '请求已完成' : '请求未完成'}</strong><span className="mono muted">{result.request.latency_ms} ms</span></div><p className="request-answer">{result.answer || result.request.error || '无可用响应'}</p><h3 className="detail-section-title">路由追踪</h3>{result.request.attempts.map((attempt, index) => <div className="attempt-row" key={index}><span className="attempt-number">{index + 1}</span><div><strong>{attempt.provider}</strong><span className="attempt-error">{attempt.error || '响应成功'}</span></div><span className={`mono ${attempt.status_code >= 400 ? 'danger-text' : 'success-text'}`}>{attempt.status_code}</span><span className="mono muted">{attempt.latency_ms} ms</span></div>)}{!result.request.attempts.length && <p className="field-note">请求未进入上游执行阶段。</p>}<p className="field-note mono">{result.request.id}</p><Link to={`/requests?q=${result.request.id}`} className="text-link" onClick={onClose}>在请求日志中查看<ArrowRight size={14} /></Link></section>}
  </Drawer>
}

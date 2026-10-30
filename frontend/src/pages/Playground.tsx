import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Alert, Button, Empty, Input, InputNumber, Select, Skeleton, Slider, Tooltip } from 'antd'
import { Bot, Check, ChevronDown, Copy, FileText, MessageSquareText, Pencil, Plus, RefreshCw, Send, Settings2, Square, Trash2, UserRound, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { errorMessage } from '../api/http'
import { getPlaygroundProviders, sendPlaygroundMessage } from '../api/playground'
import type { PlaygroundMessage, PlaygroundReply } from '../api/playground'
import { useData } from '../hooks/useData'

type SessionMessage = PlaygroundMessage & { id: string; reply?: PlaygroundReply }
type PlaygroundSession = {
  id: string
  title: string
  updatedAt: number
  providerId: string
  modelKey: string
  systemPrompt: string
  temperature: number
  maxTokens: number
  messages: SessionMessage[]
}
type PendingRequest = { sessionId: string; requestId: string }

const STORAGE_KEY = 'modelgate-playground-sessions'
const defaultSystemPrompt = '你是一个简洁、准确的模型助手。'

function createId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function createSession(providerId = '', modelKey = ''): PlaygroundSession {
  return { id: createId(), title: '新对话', updatedAt: Date.now(), providerId, modelKey, systemPrompt: defaultSystemPrompt, temperature: 0.7, maxTokens: 2048, messages: [] }
}

function readSessions(): PlaygroundSession[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    if (!Array.isArray(value)) return []
    return value.filter(item => item && typeof item.id === 'string').map(item => ({
      ...createSession(item.providerId || '', item.modelKey || ''), ...item,
      title: typeof item.title === 'string' ? item.title : '新对话',
      updatedAt: typeof item.updatedAt === 'number' ? item.updatedAt : Date.now(),
      systemPrompt: typeof item.systemPrompt === 'string' ? item.systemPrompt : defaultSystemPrompt,
      temperature: typeof item.temperature === 'number' ? item.temperature : 0.7,
      maxTokens: typeof item.maxTokens === 'number' ? item.maxTokens : 2048,
      messages: Array.isArray(item.messages) ? item.messages : [],
    }))
  } catch { return [] }
}

function shortenTitle(value: string) {
  const compact = value.replace(/\s+/g, ' ').trim()
  return compact.length > 30 ? `${compact.slice(0, 30)}…` : compact || '新对话'
}

function formatTime(timestamp: number) {
  const date = new Date(timestamp)
  const now = new Date()
  return date.toDateString() === now.toDateString()
    ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

function inlineParts(value: string): ReactNode[] {
  return value.split(/(`[^`]+`)/g).map((part, index) => part.startsWith('`') && part.endsWith('`')
    ? <code key={index}>{part.slice(1, -1)}</code>
    : <Fragment key={index}>{part}</Fragment>)
}

function renderText(value: string, key: string) {
  return <div className="pg-rich-text" key={key}>{value.split(/\n{2,}/).filter(Boolean).map((paragraph, index) => {
    const lines = paragraph.split('\n')
    return <p key={index}>{lines.map((line, lineIndex) => <Fragment key={lineIndex}>{inlineParts(line)}{lineIndex < lines.length - 1 && <br />}</Fragment>)}</p>
  })}</div>
}

function renderRichText(content: string, copyCode: (code: string) => void) {
  const nodes: ReactNode[] = []
  const codePattern = /```([^\n]*)\n([\s\S]*?)```/g
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = codePattern.exec(content))) {
    if (match.index > cursor) nodes.push(renderText(content.slice(cursor, match.index), `text-${cursor}`))
    const language = match[1].trim() || '代码'
    const code = match[2].replace(/\n$/, '')
    nodes.push(<div className="pg-code" key={`code-${match.index}`}><div className="pg-code-head"><span>{language}</span><Tooltip title="复制代码"><Button type="text" size="small" icon={<Copy size={14} />} aria-label="复制代码" onClick={() => copyCode(code)} /></Tooltip></div><pre><code>{code}</code></pre></div>)
    cursor = match.index + match[0].length
  }
  if (cursor < content.length || !nodes.length) nodes.push(renderText(content.slice(cursor), `text-${cursor}`))
  return nodes
}

export default function Playground() {
  const { data: providers, loading, error: loadError, refresh } = useData(getPlaygroundProviders)
  const [sessions, setSessions] = useState<PlaygroundSession[]>(() => readSessions())
  const [activeId, setActiveId] = useState('')
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<PendingRequest | null>(null)
  const [sendError, setSendError] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [renameId, setRenameId] = useState('')
  const [renameValue, setRenameValue] = useState('')
  const [copied, setCopied] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const available = useMemo(() => providers?.filter(provider => provider.enabled && provider.models.length) ?? [], [providers])
  const activeSession = sessions.find(session => session.id === activeId) ?? sessions[0]
  const activeProvider = available.find(provider => provider.id === activeSession?.providerId) ?? available[0]
  const activeModel = activeProvider?.models.find(model => model.public_model === activeSession?.modelKey) ?? activeProvider?.models[0]
  const contextChars = activeSession?.messages.reduce((total, message) => total + message.content.length, 0) ?? 0

  useEffect(() => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions)) } catch { /* Browser storage is optional. */ } }, [sessions])

  useEffect(() => {
    if (!providers || sessions.length || !available.length) return
    const session = createSession(available[0].id, available[0].models[0].public_model)
    setSessions([session])
    setActiveId(session.id)
  }, [available, providers, sessions.length])

  useEffect(() => { if (!activeId && sessions[0]) setActiveId(sessions[0].id) }, [activeId, sessions])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'end' }) }, [activeSession?.messages.length, pending])

  function updateSession(id: string, patch: Partial<PlaygroundSession>) {
    setSessions(current => current.map(session => session.id === id ? { ...session, ...patch, updatedAt: Date.now() } : session))
  }

  function newSession() {
    const session = createSession(activeProvider?.id, activeModel?.public_model)
    setSessions(current => [session, ...current])
    setActiveId(session.id)
    setDraft('')
    setSendError('')
    setSettingsOpen(false)
  }

  function deleteSession(id: string) {
    if (pending?.sessionId === id) abortRef.current?.abort()
    const remaining = sessions.filter(session => session.id !== id)
    const next = remaining.length ? remaining : [createSession(activeProvider?.id, activeModel?.public_model)]
    setSessions(next)
    if (id === activeSession?.id) setActiveId(next[0].id)
    setDraft('')
    setSendError('')
  }

  function startRename(session: PlaygroundSession) {
    setRenameId(session.id)
    setRenameValue(session.title)
  }

  function commitRename() {
    if (!renameId) return
    updateSession(renameId, { title: shortenTitle(renameValue) })
    setRenameId('')
  }

  function selectProvider(providerId: string) {
    const firstModel = available.find(provider => provider.id === providerId)?.models[0]?.public_model || ''
    if (activeSession) updateSession(activeSession.id, { providerId, modelKey: firstModel })
    setDraft('')
    setSendError('')
  }

  async function copyText(content: string, key = 'reply') {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(key)
      window.setTimeout(() => setCopied(current => current === key ? '' : current), 1600)
    } catch { setSendError('复制失败，请检查浏览器剪贴板权限。') }
  }

  function editMessage(message: SessionMessage) {
    if (!activeSession || message.role !== 'user') return
    setDraft(message.content)
    const index = activeSession.messages.findIndex(item => item.id === message.id)
    updateSession(activeSession.id, { messages: activeSession.messages.slice(0, index) })
  }

  function removeMessage(messageId: string) {
    if (!activeSession) return
    updateSession(activeSession.id, { messages: activeSession.messages.filter(message => message.id !== messageId) })
  }

  async function send() {
    const question = draft.trim()
    if (!question || !activeSession || !activeProvider || !activeModel || pending) return
    const requestId = createId()
    const controller = new AbortController()
    const userMessage: SessionMessage = { id: createId(), role: 'user', content: question }
    const history = activeSession.messages.slice(-62)
    const messages: PlaygroundMessage[] = [
      ...(activeSession.systemPrompt.trim() ? [{ role: 'system' as const, content: activeSession.systemPrompt.trim() }] : []),
      ...history.map(({ role, content }) => ({ role, content })),
      { role: 'user', content: question },
    ]
    setSessions(current => current.map(session => session.id === activeSession.id ? { ...session, title: session.title === '新对话' ? shortenTitle(question) : session.title, messages: [...session.messages, userMessage], updatedAt: Date.now() } : session))
    setPending({ sessionId: activeSession.id, requestId })
    abortRef.current = controller
    setDraft('')
    setSendError('')
    try {
      const reply = await sendPlaygroundMessage(activeProvider.id, activeModel.upstream_model, messages, { temperature: activeSession.temperature, max_tokens: activeSession.maxTokens, signal: controller.signal })
      const assistantMessage: SessionMessage = { id: createId(), role: 'assistant', content: reply.content, reply }
      setSessions(current => current.map(session => session.id === activeSession.id ? { ...session, messages: [...session.messages, assistantMessage], updatedAt: Date.now() } : session))
    } catch (reason) {
      setDraft(question)
      setSessions(current => current.map(session => session.id === activeSession.id ? { ...session, messages: session.messages.filter(message => message.id !== userMessage.id) } : session))
      if (!controller.signal.aborted) setSendError(errorMessage(reason))
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setPending(current => current?.requestId === requestId ? null : current)
    }
  }

  function stop() {
    abortRef.current?.abort()
    setPending(null)
  }

  if (loading && !providers) return <Skeleton active paragraph={{ rows: 12 }} />
  if (!available.length) return <><section className="page-heading"><div><h1 className="page-title">模型测试</h1><p className="page-subtitle">用对话确认你配置的上游模型是否可以正常响应。</p></div><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新上游</Button></section>{loadError && <Alert type="error" showIcon message={loadError} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 18 }} />}<div className="pg-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无已启用的上游模型" /><Link to="/providers"><Button type="primary">配置上游</Button></Link></div></>

  return <>
    <section className="page-heading pg-heading"><div><h1 className="page-title">模型测试</h1><p className="page-subtitle">像 NewAPI 调试台一样，验证指定上游的真实对话响应。</p></div><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新上游</Button></section>
    {loadError && <Alert type="error" showIcon message={loadError} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 18 }} />}
    <section className="pg-layout" aria-label="模型对话测试">
      <aside className="pg-sessions">
        <div className="pg-sessions-head"><div><strong>对话</strong><span>{sessions.length}</span></div><Tooltip title="新建对话"><Button type="text" icon={<Plus size={17} />} aria-label="新建对话" onClick={newSession} /></Tooltip></div>
        <Button className="pg-new-session" type="primary" icon={<MessageSquareText size={15} />} onClick={newSession}>新建对话</Button>
        <div className="pg-session-list">{sessions.map(session => <div className={`pg-session-item${session.id === activeSession?.id ? ' active' : ''}`} key={session.id}>
          {renameId === session.id ? <Input autoFocus size="small" value={renameValue} maxLength={30} onChange={event => setRenameValue(event.target.value)} onBlur={commitRename} onPressEnter={commitRename} onKeyDown={event => { if (event.key === 'Escape') setRenameId('') }} /> : <button type="button" className="pg-session-select" onClick={() => { setActiveId(session.id); setSendError('') }}><span className="pg-session-icon"><FileText size={14} /></span><span><strong>{session.title}</strong><small>{formatTime(session.updatedAt)} · {session.messages.filter(message => message.role === 'user').length} 条消息</small></span></button>}
          {renameId !== session.id && <span className="pg-session-actions"><Tooltip title="重命名"><Button type="text" size="small" icon={<Pencil size={13} />} aria-label={`重命名 ${session.title}`} onClick={() => startRename(session)} /></Tooltip><Tooltip title="删除"><Button type="text" danger size="small" icon={<Trash2 size={13} />} aria-label={`删除 ${session.title}`} onClick={() => deleteSession(session.id)} /></Tooltip></span>}
        </div>)}</div>
        <div className="pg-sessions-foot"><span className="status-dot" />对话保存在当前浏览器</div>
      </aside>
      <div className="pg-chat">
        <header className="pg-chat-head"><div><strong>{activeSession?.title}</strong><span>{activeSession?.messages.length ?? 0} 条消息</span></div><div className="pg-chat-actions"><span className="pg-model-status"><span className="status-dot" />已启用</span><Button type={settingsOpen ? 'primary' : 'default'} icon={<Settings2 size={15} />} onClick={() => setSettingsOpen(value => !value)}>参数</Button><Tooltip title="清空当前对话"><Button type="text" icon={<X size={16} />} aria-label="清空当前对话" disabled={!activeSession?.messages.length || !!pending} onClick={() => activeSession && updateSession(activeSession.id, { messages: [], title: '新对话' })} /></Tooltip></div></header>
        {settingsOpen && activeSession && <div className="pg-settings"><label className="pg-system-field"><span>系统提示</span><Input.TextArea value={activeSession.systemPrompt} onChange={event => updateSession(activeSession.id, { systemPrompt: event.target.value })} autoSize={{ minRows: 2, maxRows: 4 }} maxLength={16000} placeholder="可选：定义模型的行为和回答风格" /></label><div className="pg-param"><label><span>温度</span><strong>{activeSession.temperature.toFixed(1)}</strong></label><Slider min={0} max={2} step={0.1} value={activeSession.temperature} onChange={temperature => updateSession(activeSession.id, { temperature })} /></div><div className="pg-param"><label><span>最大输出 Token</span></label><InputNumber min={1} max={32768} step={128} value={activeSession.maxTokens} onChange={value => { if (typeof value === 'number') updateSession(activeSession.id, { maxTokens: value }) }} /></div><div className="pg-context"><span>当前消息 {activeSession.messages.length} 条</span><span>约 {contextChars.toLocaleString('zh-CN')} 字符</span></div></div>}
        <div className="pg-messages" role="log" aria-live="polite">
          {!activeSession?.messages.length && !pending && <div className="pg-welcome"><span><Bot size={25} strokeWidth={1.6} /></span><h2>开始测试这个模型</h2><p>{activeProvider?.name} · {activeModel?.public_model === activeModel?.upstream_model ? activeModel?.upstream_model : `${activeModel?.public_model} → ${activeModel?.upstream_model}`}</p><div className="pg-suggestions"><button type="button" onClick={() => setDraft('请用一句话介绍你自己。')}>请用一句话介绍你自己</button><button type="button" onClick={() => setDraft('写一个最小的 Python Hello World。')}>写一个最小的 Python 示例</button><button type="button" onClick={() => setDraft('把这段话总结成三点：')}>帮我总结一段文字</button><button type="button" onClick={() => setDraft('给我一个排查接口错误的思路。')}>给我一个排查思路</button></div></div>}
          {activeSession?.messages.map(message => <div className={`pg-message-row ${message.role}`} key={message.id}><span className="pg-avatar">{message.role === 'user' ? <UserRound size={16} /> : <Bot size={17} />}</span><div className="pg-message-body"><div className="pg-message-label"><strong>{message.role === 'user' ? '你' : activeProvider?.name}</strong>{message.role === 'assistant' && message.reply && <span className="muted">{message.reply.latency_ms} ms{message.reply.output_tokens !== null ? ` · ${message.reply.output_tokens} tokens` : ''}</span>}</div>{message.role === 'assistant' ? renderRichText(message.content, code => void copyText(code, message.id)) : <p className="pg-user-text">{message.content}</p>}<div className="pg-message-actions">{message.role === 'assistant' && <Tooltip title={copied === message.id ? '已复制' : '复制回复'}><Button type="text" size="small" icon={copied === message.id ? <Check size={13} /> : <Copy size={13} />} aria-label="复制回复" onClick={() => void copyText(message.content, message.id)} /></Tooltip>}{message.role === 'user' && <Tooltip title="编辑并重新发送"><Button type="text" size="small" icon={<Pencil size={13} />} aria-label="编辑消息" onClick={() => editMessage(message)} /></Tooltip>}<Tooltip title="删除消息"><Button type="text" danger size="small" icon={<Trash2 size={13} />} aria-label="删除消息" onClick={() => removeMessage(message.id)} /></Tooltip></div></div></div>)}
          {pending?.sessionId === activeSession?.id && <div className="pg-message-row assistant"><span className="pg-avatar"><Bot size={17} /></span><div className="pg-message-body"><div className="pg-message-label"><strong>{activeProvider?.name}</strong></div><p className="pg-typing">正在等待模型响应<span>•••</span></p></div></div>}
          <div ref={bottomRef} />
        </div>
        <div className="pg-composer">{sendError && <Alert type="error" showIcon message={sendError} closable onClose={() => setSendError('')} />}<div className="pg-compose-box"><Input.TextArea aria-label="对话内容" value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() } }} placeholder="输入消息，Enter 发送，Shift + Enter 换行" autoSize={{ minRows: 2, maxRows: 7 }} maxLength={16000} disabled={!!pending} /><div className="pg-compose-footer"><div className="pg-compose-selects"><Select size="small" value={activeProvider?.id} onChange={selectProvider} disabled={!!pending} options={available.map(provider => ({ value: provider.id, label: provider.name }))} aria-label="选择上游" /><ChevronDown size={13} /><Select size="small" value={activeModel?.public_model} onChange={modelKey => activeSession && updateSession(activeSession.id, { modelKey })} disabled={!!pending} options={activeProvider?.models.map(model => ({ value: model.public_model, label: model.public_model === model.upstream_model ? model.public_model : `${model.public_model} · ${model.upstream_model}` }))} aria-label="选择模型" /></div><span className="pg-compose-hint">{activeSession?.messages.length ?? 0} 条上下文</span><Button type={pending ? 'default' : 'primary'} danger={!!pending} icon={pending ? <Square size={14} /> : <Send size={16} />} disabled={!pending && !draft.trim()} onClick={pending ? stop : () => void send()}>{pending ? '停止' : '发送'}</Button></div></div><div className="pg-composer-meta"><span>请求会直接发送到选中的上游</span><span>温度 {activeSession?.temperature.toFixed(1)} · 最大 {activeSession?.maxTokens} tokens</span></div></div>
      </div>
    </section>
  </>
}

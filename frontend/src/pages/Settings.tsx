import { Alert, Button, Descriptions, Empty, Skeleton } from 'antd'
import { Check, Database, Info, RefreshCw, ShieldCheck } from 'lucide-react'
import { getSettings } from '../api/settings'
import { useData } from '../hooks/useData'

const labels: Record<string, string> = {
  mode: '运行模式', storage: '存储引擎', database: '数据库', database_path: '本地数据库路径',
  started_at: '启动时间', start_time: '启动时间', version: '版本', max_attempts: '单次请求最多尝试',
  rpm_limit: '默认每分钟请求限制', concurrency_limit: '默认并发限制', host: '监听地址', port: '端口',
  demo: '演示模式', demo_mode: '演示模式', providers: '供应商数量', model_routes: '路由数量',
  rate_limit: '请求频率限制', limits: '限制配置', routing: '路由策略', auth: '鉴权方式',
  upstream_mode: '上游模式', persistence: '持久化方式', database_engine: '数据库引擎',
  limiter: '限流方式', virtual_key_rpm: '默认虚拟密钥 RPM', streaming: 'SSE 流式响应',
  prompt_storage: '提示词保存', billing: '用量计量',
}
function display(value: unknown, key: string) {
  if ((key === 'started_at' || key === 'start_time') && typeof value === 'string') return new Date(value).toLocaleString('zh-CN', { hour12: false })
  if (typeof value === 'boolean') return value ? '已启用' : '未启用'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

export default function Settings() {
  const { data, loading, error, refresh } = useData(getSettings)
  const entries = Object.entries(data ?? {}).filter(([, value]) => value !== undefined && value !== null)
  return <>
    <section className="page-heading"><div><h1 className="page-title">设置</h1><p className="page-subtitle">查看当前网关环境、运行配置与演示能力边界。</p></div><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新配置</Button></section>
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    {loading && !data ? <Skeleton active paragraph={{ rows: 7 }} /> : data && <>
      <section className="panel"><div className="panel-head"><div className="settings-heading"><Database size={17} /><h2 className="panel-title">运行环境</h2></div><span className="plain-tag">只读</span></div><div className="panel-body">{entries.length ? <Descriptions column={1} size="middle" items={entries.map(([key, value]) => ({ key, label: labels[key] || key, children: <span className={typeof value !== 'boolean' ? 'mono' : undefined} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{display(value, key)}</span> }))} /> : <Empty description="当前环境未返回额外配置。" />}</div></section>
      <section className="panel section-gap"><div className="panel-head"><div className="settings-heading"><ShieldCheck size={17} /><h2 className="panel-title">本地 Demo 的工作方式</h2></div></div><div className="capability-list"><div><Check size={17} /><p><strong>请求真实经过调度与记录</strong><span>选路、上游切换、状态开关和调用记录均由本地后端处理。</span></p></div><div><Check size={17} /><p><strong>数据保留在本地</strong><span>SQLite 保存演示配置、虚拟 Key 元数据和请求记录。提示词正文不写入调用日志。</span></p></div><div><Info size={17} /><p><strong>模拟上游，无真实模型费用</strong><span>响应内容、延迟与 Token 为模拟数据；进程内限制用于展示，不代表分布式生产能力。</span></p></div></div></section>
      <div className="settings-footer"><Info size={16} /><p>PostgreSQL、Redis 共享限流、生产级管理员会话与完整预算治理按项目规划后续推进。此页展示运行配置，不提供环境变量编辑。</p></div>
    </>}
  </>
}

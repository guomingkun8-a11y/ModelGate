import { Activity, ArrowDown, ArrowRight, Check, Layers3, Route, Shield, Waypoints } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../stores/auth'

export default function Landing() {
  const { token } = useAuth()
  return <div className="landing-page">
    <header className="landing-header">
      <Link to="/" className="landing-brand"><Layers3 size={27} /><span>ModelGate</span></Link>
      <nav aria-label="账户"><Link className="landing-login" to="/login">登录</Link><Link className="landing-register" to={token ? '/console' : '/register'}>{token ? '进入控制台' : '创建账号'} <ArrowRight size={15} /></Link></nav>
    </header>

    <main>
      <section className="landing-hero">
        <div className="landing-copy">
          <span className="landing-kicker"><span /> 模型调用控制台</span>
          <h1>让每一次模型调用，<br />都有清晰的去向。</h1>
          <p>从一个兼容接口接入模型，集中查看路由、请求结果与用量。</p>
          <div className="landing-actions">
            <Link className="landing-cta" to={token ? '/console' : '/register'}>{token ? '打开控制台' : '开始使用'} <ArrowRight size={17} /></Link>
            <Link to={token ? '/console' : '/login'}>{token ? '进入工作区' : '已有账号，登录'}</Link>
          </div>
          <div className="landing-points"><span><Check size={15} /> OpenAI 兼容接口</span><span><Check size={15} /> 独立账号与密钥</span></div>
        </div>

        <div className="flow-stage" aria-label="模型请求经过 ModelGate 路由到上游供应商">
          <div className="flow-topline"><span>请求路径</span><span className="flow-label">流程示意</span></div>
          <div className="flow-map">
            <div className="flow-node flow-client"><span className="flow-icon"><Waypoints size={19} /></span><div><small>应用</small><strong>你的服务</strong></div><span className="flow-port" /></div>
            <div className="flow-edge"><span /><ArrowRight size={16} /></div>
            <div className="flow-node flow-gateway"><span className="flow-gateway-mark"><Layers3 size={20} /></span><div><small>网关入口</small><strong>ModelGate</strong></div><span className="flow-model">chat/completions</span></div>
            <div className="flow-branch"><div><span className="branch-line" /><span className="branch-dot" /><span className="branch-line" /></div><span>优先级 · 权重</span><div><span className="branch-line" /><span className="branch-dot" /><span className="branch-line" /></div></div>
            <div className="flow-targets"><div className="flow-provider"><span className="provider-mark provider-violet">A</span><strong>上游通道 A</strong><span className="provider-state">首选</span></div><div className="flow-provider"><span className="provider-mark provider-teal">B</span><strong>上游通道 B</strong><span className="provider-state">故障切换</span></div></div>
          </div>
          <div className="flow-bottom"><span><Route size={15} /> 统一路由</span><ArrowDown size={14} /><span><Activity size={15} /> 请求记录</span><ArrowDown size={14} /><span><Shield size={15} /> 密钥隔离</span></div>
        </div>
      </section>

      <section className="landing-capabilities" aria-label="控制台模块">
        <div><span className="capability-icon violet"><Route size={18} /></span><p><strong>路由可追踪</strong><small>查看模型与上游的映射</small></p></div>
        <div><span className="capability-icon teal"><Activity size={18} /></span><p><strong>请求有记录</strong><small>按账户查看请求与用量</small></p></div>
        <div><span className="capability-icon rose"><Shield size={18} /></span><p><strong>账户相互隔离</strong><small>密钥、日志和统计独立</small></p></div>
      </section>
    </main>
    <footer className="landing-footer"><span>ModelGate</span><span>多模型统一网关</span><span className="landing-footer-status">OpenAI 兼容接口</span></footer>
  </div>
}

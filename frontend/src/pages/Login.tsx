import { useState } from 'react'
import { Alert, Button, Form, Input } from 'antd'
import { Activity, ArrowRight, Layers3, Route, ShieldCheck } from 'lucide-react'
import { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'

export default function Login() {
  const auth = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(values: { password: string }) {
    if (loading) return
    setLoading(true)
    setError('')
    try {
      await auth.signIn(values.password)
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setLoading(false)
    }
  }

  return <div className="login-page">
    <div className="login-brand"><Layers3 size={25} />ModelGate</div>
    <section className="login-copy">
      <span className="environment-badge">本地演示版</span>
      <h1>管理模型流量，<br />从这里开始。</h1>
      <p>一个入口连接多个模型，让每次调用<br className="desktop-only" />都有清晰的路径。</p>
      <div className="login-capabilities">
        <span><Route size={18} />智能路由与故障切换</span>
        <span><Activity size={18} />可追溯的请求记录</span>
        <span><ShieldCheck size={18} />独立的虚拟密钥</span>
      </div>
    </section>
    <section className="login-form" aria-label="管理员登录">
      <div className="login-form-logo"><Layers3 size={26} /></div>
      <h2>进入控制台</h2>
      <p className="muted">使用演示账号，体验完整请求链路。</p>
      <Form layout="vertical" initialValues={{ password: 'modelgate-demo' }} onFinish={submit} requiredMark={false}>
        <Form.Item label="管理员密码" name="password" rules={[{ required: true, message: '请输入演示密码。' }]}>
          <Input.Password autoComplete="current-password" size="large" placeholder="输入演示密码" />
        </Form.Item>
        <p className="field-note">默认密码：<code>modelgate-demo</code></p>
        {error && <Alert type="error" showIcon message={error} role="alert" style={{ marginBottom: 16 }} />}
        <Button className="login-submit" type="primary" htmlType="submit" loading={loading} size="large" block>
          进入演示控制台 <ArrowRight size={17} />
        </Button>
      </Form>
      <p className="login-privacy">演示数据保存在本地，不会调用外部模型。</p>
    </section>
    <footer className="login-footer">ModelGate / Open model infrastructure</footer>
  </div>
}

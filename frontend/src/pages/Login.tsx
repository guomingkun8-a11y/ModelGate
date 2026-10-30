import { useState } from 'react'
import { Alert, Button, Form, Input } from 'antd'
import { ArrowRight, Layers3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'

export default function Login() {
  const auth = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  async function submit(values: { identifier: string; password: string }) {
    if (loading) return
    setLoading(true)
    setError('')
    try {
      await auth.signIn(values.identifier, values.password)
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setLoading(false)
    }
  }

  return <div className="login-page">
    <Link to="/" className="login-brand"><Layers3 size={25} />ModelGate</Link>
    <section className="login-form" aria-label="登录">
      <div className="login-form-logo"><Layers3 size={26} /></div>
      <h2>欢迎回来</h2>
      <p className="muted">登录 ModelGate 工作区。</p>
      <Form layout="vertical" onFinish={submit} requiredMark={false}>
        <Form.Item label="邮箱或管理员账号" name="identifier" rules={[{ required: true, whitespace: true, message: '请输入邮箱或管理员账号。' }]}>
          <Input autoComplete="username" size="large" placeholder="邮箱或管理员账号" />
        </Form.Item>
        <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码。' }]}>
          <Input.Password autoComplete="current-password" size="large" placeholder="输入密码" />
        </Form.Item>
        {error && <Alert type="error" showIcon message={error} role="alert" style={{ marginBottom: 16 }} />}
        <Button className="login-submit" type="primary" htmlType="submit" loading={loading} size="large" block>
          登录 <ArrowRight size={17} />
        </Button>
      </Form>
      <p className="auth-switch">还没有账号？<Link to="/register">创建账号</Link></p>
    </section>
    <footer className="login-footer">ModelGate / Open model infrastructure</footer>
  </div>
}

import { useState } from 'react'
import { Alert, Button, Form, Input } from 'antd'
import { ArrowRight, Layers3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'

export default function Register() {
  const auth = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(values: { email: string; name: string; password: string }) {
    if (loading) return
    setLoading(true)
    setError('')
    try {
      await auth.signUp(values.email, values.name, values.password)
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setLoading(false)
    }
  }

  return <div className="login-page">
    <Link to="/" className="login-brand"><Layers3 size={25} />ModelGate</Link>
    <section className="login-form" aria-label="创建账号">
      <div className="login-form-logo"><Layers3 size={26} /></div>
      <h2>创建账号</h2>
      <p className="muted">注册后进入独立的个人工作区。</p>
      <Form layout="vertical" onFinish={submit} requiredMark={false}>
        <Form.Item label="称呼" name="name" rules={[{ required: true, whitespace: true, max: 80, message: '请输入称呼。' }]}>
          <Input autoComplete="name" size="large" placeholder="你的名字" />
        </Form.Item>
        <Form.Item label="邮箱" name="email" rules={[{ required: true, type: 'email', message: '请输入有效的邮箱地址。' }]}>
          <Input autoComplete="email" size="large" placeholder="name@example.com" />
        </Form.Item>
        <Form.Item label="密码" name="password" rules={[{ required: true, min: 8, max: 256, message: '密码长度需为 8 到 256 个字符。' }]}>
          <Input.Password autoComplete="new-password" size="large" placeholder="至少 8 个字符" />
        </Form.Item>
        <Form.Item label="确认密码" name="confirmPassword" dependencies={['password']} rules={[{ required: true, message: '请再次输入密码。' }, ({ getFieldValue }) => ({ validator(_, value) { return !value || getFieldValue('password') === value ? Promise.resolve() : Promise.reject(new Error('两次输入的密码不一致。')) } })]}>
          <Input.Password autoComplete="new-password" size="large" placeholder="再次输入密码" />
        </Form.Item>
        {error && <Alert type="error" showIcon message={error} role="alert" style={{ marginBottom: 16 }} />}
        <Button className="login-submit" type="primary" htmlType="submit" loading={loading} size="large" block>
          创建账号 <ArrowRight size={17} />
        </Button>
      </Form>
      <p className="auth-switch">已经有账号？<Link to="/login">登录</Link></p>
    </section>
    <footer className="login-footer">ModelGate / Open model infrastructure</footer>
  </div>
}

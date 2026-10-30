import { useRef, useState } from 'react'
import { Alert, App, Button, Empty, Form, Input, InputNumber, Modal, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Copy, KeyRound, Plus, ShieldCheck } from 'lucide-react'
import { errorMessage } from '../api/http'
import { createVirtualKey, getVirtualKeys, revokeVirtualKey } from '../api/virtualKeys'
import StatusTag from '../components/StatusTag'
import { useData } from '../hooks/useData'
import type { VirtualKey } from '../types'

export default function VirtualKeys() {
  const { message, modal } = App.useApp()
  const { data, loading, error, refresh } = useData(getVirtualKeys)
  const [form] = Form.useForm<{ name: string; rpm_limit: number }>()
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [createError, setCreateError] = useState('')
  const [revoking, setRevoking] = useState<string[]>([])
  const creatingRef = useRef(false)

  function close() {
    if (creatingRef.current) return
    setOpen(false)
    setNewKey('')
    setCreateError('')
    form.resetFields()
  }
  function openCreate() {
    setNewKey('')
    setCreateError('')
    form.resetFields()
    setOpen(true)
  }
  async function create(values: { name: string; rpm_limit: number }) {
    if (creatingRef.current) return
    creatingRef.current = true
    setCreating(true)
    setCreateError('')
    try {
      const result = await createVirtualKey(values.name.trim(), values.rpm_limit)
      setNewKey(result.key)
      window.dispatchEvent(new Event('modelgate:refresh'))
      message.success('密钥已创建，请立即保存。')
    } catch (reason) {
      setCreateError(errorMessage(reason))
    } finally {
      creatingRef.current = false
      setCreating(false)
    }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(newKey); message.success('密钥已复制') }
    catch { message.error('复制失败，请手动保存。') }
  }
  function revoke(key: VirtualKey) {
    modal.confirm({
      title: '撤销密钥', content: `撤销“${key.name}”后将无法继续使用。`, okText: '确认撤销', cancelText: '取消', okButtonProps: { danger: true },
      onOk: async () => {
        setRevoking(value => [...value, key.id])
        try {
          await revokeVirtualKey(key.id)
          window.dispatchEvent(new Event('modelgate:refresh'))
          message.success('密钥已撤销')
        } catch (reason) {
          message.error(errorMessage(reason))
          throw reason
        } finally { setRevoking(value => value.filter(id => id !== key.id)) }
      },
    })
  }
  const columns: ColumnsType<VirtualKey> = [
    { title: '名称', dataIndex: 'name', render: name => <span className="key-name"><KeyRound size={16} />{name}</span> },
    { title: '密钥前缀', dataIndex: 'prefix', render: prefix => <span className="mono muted">{prefix}••••••</span> },
    { title: '状态', dataIndex: 'status', render: status => <StatusTag status={status} /> },
    { title: 'RPM 上限', dataIndex: 'rpm_limit', align: 'right' },
    { title: '请求数', dataIndex: 'total_requests', align: 'right', render: value => value.toLocaleString('zh-CN') },
    { title: '创建时间', dataIndex: 'created_at', render: value => new Date(value).toLocaleDateString('zh-CN') },
    { title: '操作', fixed: 'right', align: 'right', width: 100, render: (_, key) => <Button type="text" danger disabled={key.status === 'revoked' || revoking.includes(key.id)} loading={revoking.includes(key.id)} onClick={() => revoke(key)}>{key.status === 'revoked' ? '已撤销' : '撤销'}</Button> },
  ]
  const curl = `curl ${window.location.origin}/v1/chat/completions \\\n  -H "Authorization: Bearer sk-<你的虚拟密钥>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello"}]}'`

  return <>
    <section className="page-heading"><div><h1 className="page-title">虚拟密钥</h1><p className="page-subtitle">为应用分配独立凭据，统一管理模型访问。</p></div><Button type="primary" icon={<Plus size={16} />} onClick={openCreate}>创建密钥</Button></section>
    <div className="note-banner"><ShieldCheck size={18} /><span>虚拟密钥仅用于模型调用，与控制台管理员凭据独立。密钥明文仅在创建时显示一次。</span></div>
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    <section className="panel"><div className="panel-head"><div className="panel-title-with-count"><h2 className="panel-title">应用密钥</h2><span className="count-badge">{data?.length ?? 0}</span></div><span className="muted">{data?.filter(key => key.status === 'active').length ?? 0} 个使用中</span></div><Table<VirtualKey> rowKey="id" columns={columns} dataSource={data ?? []} loading={loading} pagination={false} size="middle" scroll={{ x: 920 }} locale={{ emptyText: <Empty description="还没有虚拟密钥，创建一枚来接入你的应用。" /> }} /></section>
    <section className="panel code-example"><div className="panel-head"><h2 className="panel-title">在应用中调用</h2><span className="plain-tag">OpenAI 兼容</span></div><pre><code>{curl}</code></pre></section>
    <Modal title="创建虚拟密钥" open={open} onCancel={close} maskClosable={false} closable={!creating} keyboard={!creating} destroyOnHidden footer={newKey ? <Button type="primary" onClick={close}>已保存，关闭</Button> : <><Button disabled={creating} onClick={close}>取消</Button><Button type="primary" loading={creating} onClick={() => form.submit()}>创建密钥</Button></>}>
      {newKey ? <><Alert type="warning" showIcon message="请立即保存，关闭窗口后将无法再次查看明文。" /><div className="new-key-display"><code>{newKey}</code><Button type="text" icon={<Copy size={17} />} aria-label="复制新密钥" onClick={copy} /></div></> : <Form form={form} layout="vertical" initialValues={{ name: '', rpm_limit: 60 }} onFinish={create} requiredMark={false} disabled={creating}>
        <Form.Item label="名称" name="name" rules={[{ required: true, whitespace: true, message: '请输入密钥名称。' }, { max: 60, message: '名称最多 60 个字符。' }]}><Input maxLength={60} autoComplete="off" placeholder="例如：开发环境应用" /></Form.Item>
        <Form.Item label="每分钟请求上限" name="rpm_limit" rules={[{ required: true, type: 'number', min: 1, max: 1000, message: '请输入 1–1000 之间的整数。' }]}><InputNumber min={1} max={1000} precision={0} aria-label="每分钟请求上限" /></Form.Item>
        <p className="field-note">当前使用单进程限流，共享额度后续接入 Redis。</p>
        {createError && <Alert type="error" showIcon message={createError} />}
      </Form>}
    </Modal>
  </>
}

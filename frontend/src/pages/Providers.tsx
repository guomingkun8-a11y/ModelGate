import { useState } from 'react'
import { Alert, App, AutoComplete, Button, Empty, Form, Input, InputNumber, Modal, Skeleton, Space, Switch, Table, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Check, CircleHelp, Plus, RefreshCw, Server, Trash2, Wifi } from 'lucide-react'
import { createProvider, deleteProvider, getProviders, publishProvider, testProvider, updateProvider } from '../api/providers'
import type { ProviderInput } from '../api/providers'
import { errorMessage } from '../api/http'
import StatusTag from '../components/StatusTag'
import { useData } from '../hooks/useData'
import { useAuth } from '../stores/auth'
import type { Provider, ProviderRecord, PublicProvider } from '../types'

type ProviderForm = ProviderInput & { api_key: string }

const initialValues: ProviderForm = {
  name: '', base_url: '', api_key: '', priority: 100, weight: 100,
  models: [{ public_model: '', upstream_model: '' }],
}

export default function Providers() {
  const { message, modal } = App.useApp()
  const { role } = useAuth()
  const { data, loading, error, refresh } = useData<ProviderRecord[]>(getProviders)
  const [form] = Form.useForm<ProviderForm>()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Provider>()
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testError, setTestError] = useState('')
  const [modelChoices, setModelChoices] = useState<string[]>([])
  const [busy, setBusy] = useState<string[]>([])

  function openCreate() {
    setEditing(undefined)
    setTestError('')
    setModelChoices([])
    form.setFieldsValue(initialValues)
    setOpen(true)
  }

  function openEdit(provider: Provider) {
    setEditing(provider)
    setTestError('')
    setModelChoices(provider.models.map(model => model.upstream_model))
    form.setFieldsValue({
      name: provider.name, base_url: provider.base_url, api_key: '',
      priority: provider.priority, weight: provider.weight,
      models: provider.models.map(model => ({ ...model })),
    })
    setOpen(true)
  }

  function close() {
    if (saving) return
    setOpen(false)
    setEditing(undefined)
    setTestError('')
  }

  async function save(values: ProviderForm) {
    setSaving(true)
    try {
      const input: ProviderInput = {
        name: values.name.trim(), base_url: values.base_url.trim(),
        api_key: values.api_key || undefined,
        priority: values.priority, weight: values.weight,
        models: values.models.map(model => ({
          public_model: model.public_model.trim(), upstream_model: model.upstream_model.trim(),
        })),
      }
      if (editing) await updateProvider(editing.id, input)
      else await createProvider(input)
      message.success(editing ? '上游配置已保存' : '上游已添加')
      setOpen(false)
      window.dispatchEvent(new Event('modelgate:refresh'))
    } catch (reason) {
      message.error(errorMessage(reason))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(provider: Provider, enabled: boolean) {
    setBusy(value => [...value, provider.id])
    try {
      await updateProvider(provider.id, { enabled })
      message.success(`${provider.name} 已${enabled ? '启用' : '停用'}`)
      window.dispatchEvent(new Event('modelgate:refresh'))
    } catch (reason) {
      message.error(errorMessage(reason))
    } finally {
      setBusy(value => value.filter(id => id !== provider.id))
    }
  }

  function publish(provider: Provider) {
    modal.confirm({
      title: '发布渠道到平台',
      content: `发布“${provider.name}”后，该渠道及其上游 API 凭据将用于所有客户的模型请求。确认将此旧私有渠道设为平台共享渠道？`,
      okText: '发布并共享', cancelText: '取消', okButtonProps: { danger: true },
      onOk: async () => {
        setBusy(value => [...value, provider.id])
        try {
          await publishProvider(provider.id)
          message.success('渠道已发布到平台')
          window.dispatchEvent(new Event('modelgate:refresh'))
        } catch (reason) {
          message.error(errorMessage(reason))
          throw reason
        } finally {
          setBusy(value => value.filter(id => id !== provider.id))
        }
      },
    })
  }

  async function checkConnection() {
    setTesting(true)
    setTestError('')
    try {
      const values = await form.validateFields(['base_url', 'api_key'])
      const result = await testProvider({
        provider_id: editing?.id, base_url: values.base_url.trim(),
        api_key: values.api_key || undefined,
      })
      const choices = result.models
      setModelChoices(choices)
      if (!form.getFieldValue('models')?.length) {
        form.setFieldValue('models', choices.map(model => ({ public_model: model, upstream_model: model })))
      }
      message.success(`连接成功，检测到 ${choices.length} 个模型`)
    } catch (reason) {
      if (reason && typeof reason === 'object' && 'errorFields' in reason) return
      setTestError(errorMessage(reason))
    } finally {
      setTesting(false)
    }
  }

  function remove(provider: Provider) {
    modal.confirm({
      title: '删除上游', content: `删除“${provider.name}”后，该上游从相关模型路由中移除。`,
      okText: '删除', cancelText: '取消', okButtonProps: { danger: true },
      onOk: async () => {
        setBusy(value => [...value, provider.id])
        try {
          await deleteProvider(provider.id)
          message.success('上游已删除')
          window.dispatchEvent(new Event('modelgate:refresh'))
        } catch (reason) {
          message.error(errorMessage(reason))
          throw reason
        } finally {
          setBusy(value => value.filter(id => id !== provider.id))
        }
      },
    })
  }

  const adminColumns: ColumnsType<Provider> = [
    { title: '上游', dataIndex: 'name', width: 185, render: (_, provider) => <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}><span className="provider-avatar"><Server size={17} /></span><div><strong>{provider.name}</strong><small className="table-secondary">OpenAI 兼容接口</small></div></div> },
    { title: 'Base URL', dataIndex: 'base_url', width: 250, ellipsis: true, render: value => <span className="mono">{value}</span> },
    { title: '对外模型 / 上游模型', dataIndex: 'models', width: 300, render: (models: Provider['models']) => <div className="provider-model-list">{models.map(model => <div key={`${model.public_model}:${model.upstream_model}`}><code>{model.public_model}</code>{model.public_model !== model.upstream_model && <span className="muted"> ← {model.upstream_model}</span>}</div>)}</div> },
    { title: '上游 Key', dataIndex: 'has_api_key', width: 100, render: value => <span className="muted">{value ? '已加密保存' : '未配置'}</span> },
    { title: '路由优先级 / 权重', render: (_, provider) => <span className="mono">{provider.priority} <span className="muted">/ {provider.weight}</span></span> },
    { title: '发布状态', width: 135, render: (_, provider) => provider.owner_id === null ? <Tag color="green">平台共享</Tag> : <Tag color="gold">未发布（旧私有）</Tag> },
    { title: '状态', render: (_, provider) => <StatusTag status={provider.enabled ? provider.status : 'disabled'} /> },
    { title: '启用', width: 90, render: (_, provider) => provider.owner_id !== null ? <span className="muted">发布后可管理</span> : <Switch size="small" checked={provider.enabled} loading={busy.includes(provider.id)} disabled={busy.includes(provider.id)} aria-label={`${provider.enabled ? '停用' : '启用'} ${provider.name}`} onChange={enabled => toggle(provider, enabled)} /> },
    { title: '操作', fixed: 'right', align: 'right', width: 160, render: (_, provider) => provider.owner_id !== null ? <Button type="link" danger disabled={busy.includes(provider.id)} loading={busy.includes(provider.id)} onClick={() => publish(provider)}>发布到平台</Button> : <Space size={2}><Button type="link" disabled={busy.includes(provider.id)} onClick={() => openEdit(provider)}>编辑</Button><Tooltip title="删除渠道"><Button type="link" danger icon={<Trash2 size={14} />} aria-label={`删除 ${provider.name}`} disabled={busy.includes(provider.id)} loading={busy.includes(provider.id)} onClick={() => remove(provider)} /></Tooltip></Space> },
  ]

  const publicColumns: ColumnsType<PublicProvider> = [
    { title: '渠道', dataIndex: 'name', width: 220, render: (_, provider) => <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}><span className="provider-avatar"><Server size={17} /></span><div><strong>{provider.name}</strong><small className="table-secondary">{provider.kind}</small></div></div> },
    { title: '可用模型', dataIndex: 'models', render: (models: PublicProvider['models']) => <div className="provider-model-list">{models.map(model => <code key={model.public_model}>{model.public_model}</code>)}</div> },
    { title: '状态', width: 120, render: (_, provider) => <StatusTag status={provider.enabled ? provider.status : 'disabled'} /> },
  ]

  const managedProviders = (data ?? []).filter((provider): provider is Provider => 'base_url' in provider)
  const publicProviders = (data ?? []).map(provider => ({
    id: provider.id,
    name: provider.name,
    kind: provider.kind,
    models: provider.models.map(model => ({ public_model: model.public_model })),
    enabled: provider.enabled,
    status: provider.status,
  }))

  return <>
    <section className="page-heading"><div><h1 className="page-title">{role === 'admin' ? '渠道管理' : '可用渠道'}</h1><p className="page-subtitle">{role === 'admin' ? '统一配置模型渠道和公开模型，用户通过虚拟密钥使用已发布模型。' : '查看平台开放的模型渠道和公开模型；上游配置由管理员统一维护。'}</p></div><div className="page-actions"><Button icon={<RefreshCw size={15} />} loading={loading} onClick={refresh}>刷新</Button>{role === 'admin' && <Button type="primary" icon={<Plus size={16} />} onClick={openCreate}>添加渠道</Button>}</div></section>
    {role === 'admin' && <div className="note-banner"><CircleHelp size={17} /><span>支持 OpenAI Chat Completions 兼容接口，例如 OpenAI、DeepSeek 和兼容中转服务。上游 Key 加密存储，列表和编辑页面不会显示明文。旧私有渠道不会用于客户请求，发布为平台共享前会要求确认。</span></div>}
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={refresh}>重试</Button>} style={{ marginBottom: 20 }} />}
    {loading && !data ? <Skeleton active paragraph={{ rows: 7 }} /> : <section className="panel"><div className="panel-head"><div className="panel-title-with-count"><h2 className="panel-title">{role === 'admin' ? '已配置渠道' : '平台可用渠道'}</h2><span className="count-badge">{data?.length ?? 0}</span></div><span className="muted">{role === 'admin' ? '启用状态不代表上游已通过健康检查' : '仅显示管理员已发布的公开模型和渠道状态'}</span></div>{role === 'admin' ? <Table<Provider> rowKey="id" columns={adminColumns} dataSource={managedProviders} loading={loading} pagination={false} scroll={{ x: 1180 }} size="middle" locale={{ emptyText: <Empty description="还没有渠道，添加一个兼容 OpenAI 的模型服务开始使用。" /> }} /> : <Table<PublicProvider> rowKey="id" columns={publicColumns} dataSource={publicProviders} loading={loading} pagination={false} size="middle" locale={{ emptyText: <Empty description="管理员尚未发布可用渠道或模型。" /> }} />}</section>}

    {role === 'admin' && <Modal title={editing ? '编辑渠道' : '添加渠道'} open={open} centered onCancel={close} maskClosable={!saving} closable={!saving} keyboard={!saving} forceRender width={760} styles={{ body: { maxHeight: 'calc(100dvh - 240px)', overflowY: 'auto' } }} footer={<><Button disabled={saving} onClick={close}>取消</Button><Button type="primary" loading={saving} onClick={() => form.submit()}>{editing ? '保存配置' : '添加渠道'}</Button></>}>
      <Form form={form} layout="vertical" initialValues={initialValues} onFinish={save} requiredMark={false} disabled={saving}>
        <Form.Item label="供应商名称" name="name" rules={[{ required: true, whitespace: true, message: '请输入供应商名称。' }, { max: 128, message: '名称最多 128 个字符。' }]}><Input maxLength={128} placeholder="例如：DeepSeek" /></Form.Item>
        <Form.Item label="Base URL" name="base_url" rules={[{ required: true, whitespace: true, message: '请输入上游 API 根地址。' }, { type: 'url', message: '请输入有效的 HTTPS 地址。' }, { max: 512, message: '地址最多 512 个字符。' }]}><Input placeholder="https://api.example.com/v1" /></Form.Item>
        <Form.Item label="上游 API Key" name="api_key" extra={editing ? '留空会继续使用当前已保存的 Key。' : '不需要鉴权的兼容服务可以留空。'}><Input.Password autoComplete="new-password" placeholder={editing ? '留空以保留当前 Key' : 'sk-...'} /></Form.Item>
        <div className="provider-form-test"><Button icon={<Wifi size={15} />} loading={testing} onClick={checkConnection}>测试连接并获取模型</Button><span className="field-note">需要上游支持 GET /models；模型 ID 也可以手动填写。</span></div>
        {testError && <Alert type="error" showIcon message={testError} style={{ marginBottom: 16 }} />}
        <Form.List name="models" rules={[{ validator: async (_, models: Provider['models']) => { if (!models?.length) throw new Error('至少配置一个模型。') } }]}>
          {(fields, { add, remove: removeModel }, { errors }) => <>
            <div className="provider-model-form-head"><div><span className="form-label">模型映射</span><p className="field-note">公开模型名供你的虚拟密钥调用；上游模型 ID 必须与服务商实际 ID 一致。</p></div><Button type="dashed" icon={<Plus size={14} />} onClick={() => add({ public_model: '', upstream_model: '' })}>添加模型</Button></div>
            {fields.map(field => <div className="provider-model-form-row" key={field.key}>
              <Form.Item name={[field.name, 'public_model']} rules={[{ required: true, whitespace: true, message: '请填写公开模型名。' }, { max: 128, message: '最多 128 个字符。' }]}><Input aria-label="公开模型名" placeholder="例如：chat-fast" /></Form.Item>
              <Form.Item name={[field.name, 'upstream_model']} rules={[{ required: true, whitespace: true, message: '请选择或填写上游模型 ID。' }, { max: 128, message: '最多 128 个字符。' }]}><AutoComplete aria-label="上游模型 ID" options={modelChoices.map(model => ({ value: model }))} placeholder="选择或输入模型 ID" /></Form.Item>
              <Button type="text" danger icon={<Trash2 size={15} />} aria-label="移除此模型" disabled={fields.length === 1} onClick={() => removeModel(field.name)} />
            </div>)}
            <Form.ErrorList errors={errors} />
          </>}
        </Form.List>
        <div className="provider-form-limits"><Form.Item label="路由优先级" name="priority" rules={[{ required: true, type: 'number', min: 1, max: 1000, message: '填写 1–1000 的整数。' }]}><InputNumber min={1} max={1000} precision={0} /></Form.Item><Form.Item label="同级权重" name="weight" rules={[{ required: true, type: 'number', min: 1, max: 1000, message: '填写 1–1000 的整数。' }]}><InputNumber min={1} max={1000} precision={0} /></Form.Item></div>
        <p className="field-note provider-security-note"><Check size={14} />默认只允许公网 HTTPS 上游；连接测试和模型请求均由网关服务器发起。</p>
      </Form>
    </Modal>}
  </>
}

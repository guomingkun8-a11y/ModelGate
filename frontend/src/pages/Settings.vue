<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { AlertCircle, Check, Database, Info, RefreshCw, ShieldCheck } from 'lucide-vue-next'
import { getSettings } from '../api/settings'
import { errorMessage } from '../api/http'

const settings = ref<Record<string, unknown>>({})
const loading = ref(true)
const error = ref('')
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
const entries = computed(() => Object.entries(settings.value).filter(([, value]) => value !== undefined && value !== null))
function display(value: unknown, key: string) {
  if ((key === 'started_at' || key === 'start_time') && typeof value === 'string') {
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
  }
  if (typeof value === 'boolean') return value ? '已启用' : '未启用'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}
async function load() {
  loading.value = true
  error.value = ''
  try { settings.value = await getSettings() }
  catch (reason) { error.value = errorMessage(reason) }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div>
    <div class="page-heading"><div><h1 class="page-title">设置</h1><p class="page-subtitle">查看当前网关环境、运行配置与演示能力边界。</p></div><button class="btn btn-secondary" :disabled="loading" @click="load"><RefreshCw :size="15" /> 刷新配置</button></div>
    <div v-if="error" class="error-state"><AlertCircle :size="20" /><span>{{ error }}</span><button class="btn btn-secondary" @click="load">重新加载</button></div>
    <el-skeleton v-else-if="loading" :rows="7" animated />
    <template v-else>
      <section class="panel"><div class="panel-head"><div class="settings-heading"><Database :size="17" /><h2 class="panel-title">运行环境</h2></div><span class="tag">只读</span></div><dl class="settings-list"><div v-for="[key, value] in entries" :key="key" class="settings-row"><dt>{{ labels[key] || key }}</dt><dd :class="{ mono: typeof value !== 'boolean' }">{{ display(value, key) }}</dd></div></dl><div v-if="!entries.length" class="empty-state">当前环境未返回额外配置。</div></section>
      <section class="panel section-gap"><div class="panel-head"><div class="settings-heading"><ShieldCheck :size="17" /><h2 class="panel-title">本地 Demo 的工作方式</h2></div></div><div class="capability-list"><div><Check :size="17" /><p><strong>请求真实经过调度与记录</strong><span>选路、上游切换、状态开关和调用记录均由本地后端处理。</span></p></div><div><Check :size="17" /><p><strong>数据保留在本地</strong><span>SQLite 保存演示配置、虚拟 Key 元数据和请求记录。提示词正文不写入调用日志。</span></p></div><div><Info :size="17" /><p><strong>模拟上游，无真实模型费用</strong><span>响应内容、延迟与 Token 为模拟数据；进程内限制用于展示，不代表分布式生产能力。</span></p></div></div></section>
      <div class="settings-footer"><Info :size="16" /><p>PostgreSQL、Redis 共享限流、生产级管理员会话与完整预算治理按项目规划后续推进。此页展示运行配置，不提供环境变量编辑。</p></div>
    </template>
  </div>
</template>

<style scoped>
.settings-heading{display:flex;align-items:center;gap:10px}.settings-heading svg{color:var(--primary)}.settings-list{padding:0 24px;margin:0}.settings-row{display:grid;grid-template-columns:210px 1fr;padding:18px 0;gap:18px;align-items:start;border-bottom:1px solid var(--border)}.settings-row:last-child{border-bottom:0}.settings-row dt{font-size:13px;color:var(--muted)}.settings-row dd{margin:0;font-size:12px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}.capability-list{padding:6px 24px}.capability-list>div{display:flex;align-items:flex-start;gap:12px;padding:17px 0}.capability-list svg{margin-top:2px;flex-shrink:0;color:var(--primary)}.capability-list p{margin:0;display:flex;flex-direction:column;gap:7px}.capability-list strong{font-size:13px;font-weight:550}.capability-list span{font-size:12px;color:var(--muted);line-height:1.8}.settings-footer{display:flex;align-items:flex-start;gap:10px;margin-top:20px;padding:15px 0;color:var(--muted);font-size:12px;line-height:1.8}.settings-footer svg{flex-shrink:0;margin-top:3px}.settings-footer p{margin:0;max-width:90ch}@media(max-width:600px){.settings-row{grid-template-columns:1fr;gap:7px;padding:15px 0}.settings-list,.capability-list{padding-left:18px;padding-right:18px}}
</style>

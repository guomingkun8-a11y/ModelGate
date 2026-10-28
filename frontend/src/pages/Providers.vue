<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { AlertCircle, ArrowUpRight, RefreshCw, Server } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { getProviders, updateProvider } from '../api/providers'
import type { Provider } from '../types'
import StatusTag from '../components/StatusTag.vue'

const providers = ref<Provider[]>([])
const loading = ref(true)
const error = ref('')
const updating = ref<string[]>([])
const enabledCount = computed(() => providers.value.filter((item) => item.enabled).length)

async function load() {
  loading.value = true
  error.value = ''
  try { providers.value = await getProviders() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '无法读取供应商，请确认后端已启动。' }
  finally { loading.value = false }
}

async function toggle(provider: Provider, value: string | number | boolean) {
  updating.value.push(provider.id)
  try {
    const updated = await updateProvider(provider.id, { enabled: Boolean(value) })
    const index = providers.value.findIndex((item) => item.id === provider.id)
    providers.value[index] = updated
    ElMessage.success(`${provider.name} 已${value ? '启用' : '停用'}`)
  } catch (reason) {
    ElMessage.error(reason instanceof Error ? reason.message : '供应商状态更新失败')
  } finally { updating.value = updating.value.filter((id) => id !== provider.id) }
}

function percent(value: number) { return `${value.toFixed(1)}%` }
onMounted(() => { load(); window.addEventListener('modelgate:refresh', load) })
onUnmounted(() => window.removeEventListener('modelgate:refresh', load))
</script>

<template>
  <div>
    <div class="page-heading">
      <div><h1 class="page-title">供应商</h1><p class="page-subtitle">管理模型上游，观察每一条调用通道的可用状态。</p></div>
      <button class="btn btn-secondary" :disabled="loading" @click="load"><RefreshCw :size="15" /> 刷新状态</button>
    </div>
    <div v-if="error" class="error-state"><AlertCircle :size="20" /><span>{{ error }}</span><button class="btn btn-secondary" @click="load">重新加载</button></div>
    <el-skeleton v-else-if="loading" :rows="7" animated />
    <template v-else>
      <div class="provider-summary"><span><Server :size="16" /> 供应商通道</span><strong>{{ enabledCount }} <span class="muted">/ {{ providers.length }} 已启用</span></strong><span class="muted">此环境的所有上游均为本地模拟，不访问外部服务。</span></div>
      <section class="panel">
        <div class="panel-head"><h2 class="panel-title">上游连接</h2><span class="muted">状态变更即时生效</span></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>供应商</th><th>支持模型</th><th>状态</th><th>模拟延迟</th><th>成功率</th><th>优先级 / 权重</th><th>启用</th></tr></thead>
            <tbody>
              <tr v-for="provider in providers" :key="provider.id">
                <td><div class="provider-name"><span class="provider-avatar"><Server :size="17" /></span><div><strong>{{ provider.name }}</strong><small class="muted mono">{{ provider.kind }}</small></div></div></td>
                <td><div class="model-tags"><span v-for="model in provider.models" :key="model" class="tag mono">{{ model }}</span></div></td>
                <td><StatusTag :status="provider.enabled ? provider.status : 'disabled'" /></td>
                <td class="mono">{{ provider.latency_ms.toLocaleString() }} <span class="muted">ms</span></td>
                <td class="mono">{{ percent(provider.success_rate) }}</td>
                <td class="mono">{{ provider.priority }} <span class="muted">/ {{ provider.weight }}</span></td>
                <td><el-switch :model-value="provider.enabled" :loading="updating.includes(provider.id)" :aria-label="`${provider.enabled ? '停用' : '启用'} ${provider.name}`" @change="toggle(provider, $event)" /></td>
              </tr>
            </tbody>
          </table>
          <div v-if="!providers.length" class="empty-state">尚未配置供应商，请通过初始化脚本添加演示上游。</div>
        </div>
      </section>
      <section class="provider-note"><ArrowUpRight :size="18" /><div><strong>试试关闭主通道</strong><p>停用高优先级上游后，再发起一个测试请求，可在请求日志中查看新的路由结果。关闭全部通道时，请求会明确返回不可用。</p></div></section>
    </template>
  </div>
</template>

<style scoped>
.provider-summary{display:flex;align-items:center;gap:20px;margin:0 0 22px;font-size:13px}.provider-summary>span:first-child{display:flex;align-items:center;gap:8px}.provider-summary>span:last-child{margin-left:auto;font-size:12px}.provider-summary strong{font-size:16px;font-weight:600}.provider-summary strong span{font-size:12px;font-weight:400}.provider-name{display:flex;align-items:center;gap:11px}.provider-name strong{font-weight:550}.provider-name small{display:block;margin-top:5px;font-size:11px}.provider-avatar{display:grid;place-items:center;width:36px;height:36px;border:1px solid var(--border);border-radius:9px;color:var(--primary);background:var(--surface)}.model-tags{display:flex;gap:5px;flex-wrap:wrap;max-width:230px}.model-tags .tag{font-size:11px}.provider-note{display:flex;align-items:flex-start;gap:12px;margin-top:22px;padding:18px 20px;border:1px solid var(--border);border-radius:10px;background:var(--surface);font-size:13px;color:var(--muted)}.provider-note>svg{flex-shrink:0;color:var(--primary)}.provider-note strong{font-weight:550;color:var(--ink)}.provider-note p{margin:6px 0 0;line-height:1.7;max-width:85ch}@media(max-width:760px){.provider-summary{align-items:flex-start;flex-wrap:wrap;gap:10px 20px}.provider-summary>span:last-child{margin-left:0;flex-basis:100%}}
</style>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { AlertCircle, ArrowRight, GitBranch, RefreshCw, Server } from 'lucide-vue-next'
import { getModelRoutes } from '../api/modelRoutes'
import { getProviders } from '../api/providers'
import type { ModelRoute, Provider } from '../types'
import StatusTag from '../components/StatusTag.vue'

const routes = ref<ModelRoute[]>([])
const providers = ref<Provider[]>([])
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try { [routes.value, providers.value] = await Promise.all([getModelRoutes(), getProviders()]) }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '模型路由加载失败，请重试。' }
  finally { loading.value = false }
}
function routeProviders(route: ModelRoute) {
  return route.provider_ids.map((id) => providers.value.find((provider) => provider.id === id)).filter((item): item is Provider => Boolean(item)).sort((a, b) => b.priority - a.priority)
}
onMounted(() => { load(); window.addEventListener('modelgate:refresh', load) })
onUnmounted(() => window.removeEventListener('modelgate:refresh', load))
</script>

<template>
  <div>
    <div class="page-heading"><div><h1 class="page-title">模型路由</h1><p class="page-subtitle">一个模型入口，连接多个供应商。按优先级分配，失败时自动切换。</p></div><button class="btn btn-secondary" :disabled="loading" @click="load"><RefreshCw :size="15" /> 刷新路由</button></div>
    <div v-if="error" class="error-state"><AlertCircle :size="20" /><span>{{ error }}</span><button class="btn btn-secondary" @click="load">重新加载</button></div>
    <el-skeleton v-else-if="loading" :rows="8" animated />
    <template v-else>
      <div class="route-label"><span>{{ routes.length }} 条模型路由</span><span class="muted">只读配置 · 通过演示请求验证选路</span></div>
      <section v-for="route in routes" :key="route.id" class="panel route-panel">
        <div class="panel-head"><div class="route-heading"><GitBranch :size="18" /><h2 class="panel-title">{{ route.name || route.model }}</h2><span class="tag mono">{{ route.model }}</span></div><StatusTag :status="route.enabled ? 'active' : 'disabled'" /></div>
        <div class="route-body">
          <div class="route-entry"><span class="muted">公开模型名</span><strong class="mono">{{ route.model }}</strong><span class="tag">OpenAI 兼容接口</span></div>
          <div class="route-connector"><span class="route-line"></span><ArrowRight :size="18" /><span class="route-line"></span></div>
          <div class="route-targets"><div v-for="provider in routeProviders(route)" :key="provider.id" class="route-target"><span class="route-provider-icon"><Server :size="17" /></span><div class="route-target-name"><strong>{{ provider.name }}</strong><span class="muted">优先级 {{ provider.priority }} · 权重 {{ provider.weight }}</span></div><StatusTag :status="provider.enabled ? provider.status : 'disabled'" /></div><div v-if="!routeProviders(route).length" class="empty-state">此路由暂无上游。</div></div>
        </div>
        <div class="route-footer"><span>路由策略 <strong>{{ route.strategy || '优先级 + 权重' }}</strong></span><span>最多尝试 <strong>3 个不同上游</strong></span><span class="muted">SSE 开始后不再切换</span></div>
      </section>
      <div v-if="!routes.length" class="panel empty-state">没有模型路由，请先初始化演示配置。</div>
    </template>
  </div>
</template>

<style scoped>
.route-label{display:flex;justify-content:space-between;font-size:13px;margin-bottom:16px}.route-panel{margin-bottom:20px}.route-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.route-heading>svg{color:var(--primary)}.route-heading>.tag{font-size:11px;font-weight:400}.route-body{display:flex;align-items:center;padding:28px 32px;gap:24px}.route-entry{min-width:170px;display:flex;flex-direction:column;align-items:flex-start;gap:12px}.route-entry>.muted{font-size:12px}.route-entry strong{font-size:17px;font-weight:550}.route-entry .tag{font-size:11px}.route-connector{display:flex;align-items:center;min-width:60px;flex:1;max-width:180px;color:var(--muted);gap:2px}.route-line{height:1px;flex:1;background:var(--border)}.route-targets{display:grid;gap:10px;flex:1;max-width:540px}.route-target{display:flex;align-items:center;gap:12px;padding:14px 16px;border:1px solid var(--border);border-radius:8px}.route-provider-icon{display:grid;place-items:center;width:30px;height:30px;background:var(--surface);border-radius:7px;color:var(--primary)}.route-target-name{display:flex;flex:1;flex-direction:column;gap:5px}.route-target-name strong{font-size:13px;font-weight:550}.route-target-name .muted{font-size:11px}.route-footer{display:flex;gap:24px;flex-wrap:wrap;padding:13px 24px;background:var(--surface);border-top:1px solid var(--border);font-size:12px;color:var(--muted);border-radius:0 0 10px 10px}.route-footer strong{color:var(--ink);font-weight:500;margin-left:6px}.route-footer>.muted:last-child{margin-left:auto}@media(max-width:760px){.route-body{padding:20px;gap:15px;flex-direction:column;align-items:stretch}.route-entry{min-width:0}.route-connector{min-height:22px;align-self:center;transform:rotate(90deg);width:50px;flex:none}.route-targets{max-width:none}.route-footer{gap:10px}.route-footer>.muted:last-child{margin-left:0}.route-label{flex-wrap:wrap;gap:8px}}
</style>

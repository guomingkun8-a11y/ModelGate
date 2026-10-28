<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { AlertCircle, Info, RefreshCw } from 'lucide-vue-next'
import { getUsage } from '../api/usage'
import type { UsageData } from '../types'
import StatCard from '../components/StatCard.vue'
import TrendChart from '../components/TrendChart.vue'

const usage = ref<UsageData | null>(null)
const hours = ref(24)
const loading = ref(true)
const error = ref('')
const format = (value: number) => Intl.NumberFormat('zh-CN').format(value)
const models = computed(() => [...(usage.value?.by_model || [])].sort((a, b) => b.tokens - a.tokens))
function share(tokens: number) { return usage.value?.total_tokens ? (tokens / usage.value.total_tokens * 100).toFixed(1) : '0.0' }

async function load() {
  loading.value = true
  error.value = ''
  try { usage.value = await getUsage(hours.value) }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '用量加载失败，请重试。' }
  finally { loading.value = false }
}
watch(hours, load)
onMounted(() => { load(); window.addEventListener('modelgate:refresh', load) })
onUnmounted(() => window.removeEventListener('modelgate:refresh', load))
</script>

<template>
  <div>
    <div class="page-heading"><div><h1 class="page-title">用量分析</h1><p class="page-subtitle">了解请求与 Token 的分布，为模型使用提供可追溯的数据。</p></div><div class="usage-actions"><el-select v-model="hours" aria-label="用量时间范围" style="width:132px"><el-option :value="1" label="最近 1 小时" /><el-option :value="24" label="最近 24 小时" /><el-option :value="168" label="最近 7 天" /></el-select><button class="btn btn-secondary" :disabled="loading" @click="load"><RefreshCw :size="15" /> 刷新</button></div></div>
    <div v-if="error" class="error-state"><AlertCircle :size="20" /><span>{{ error }}</span><button class="btn btn-secondary" @click="load">重新加载</button></div>
    <el-skeleton v-else-if="loading" :rows="9" animated />
    <template v-else-if="usage">
      <div class="usage-stats"><StatCard label="总请求数" :value="format(usage.total_requests)" description="所选时间范围内" /><StatCard label="输入 Token" :value="format(usage.input_tokens)" description="模拟请求输入估算" /><StatCard label="输出 Token" :value="format(usage.output_tokens)" description="模拟响应输出估算" /><StatCard label="总 Token" :value="format(usage.total_tokens)" description="输入与输出合计" /></div>
      <section class="panel section-gap"><div class="panel-head"><h2 class="panel-title">请求趋势</h2><span class="muted">所选时间范围内的请求分布</span></div><div class="panel-body"><TrendChart :series="usage.series" /></div></section>
      <section class="panel section-gap"><div class="panel-head"><h2 class="panel-title">按模型分布</h2><span class="muted">{{ models.length }} 个模型</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>模型</th><th>请求次数</th><th>Token 用量</th><th>用量占比</th></tr></thead><tbody><tr v-for="model in models" :key="model.model"><td><strong class="mono">{{ model.model }}</strong></td><td class="mono">{{ format(model.requests) }}</td><td class="mono">{{ format(model.tokens) }}</td><td><div class="share-cell"><span class="mono">{{ share(model.tokens) }}%</span><meter :value="model.tokens" :max="Math.max(usage.total_tokens, 1)" :aria-label="`${model.model} Token 用量占比`"></meter></div></td></tr></tbody></table><div v-if="!models.length" class="empty-state">所选时间范围暂无调用，发起一个测试请求后即可查看用量。</div></div></section>
      <p class="usage-note"><Info :size="15" /> 此处 Token 均来自模拟请求估算，用于演示用量分析，不作为真实模型账单依据。</p>
    </template>
  </div>
</template>

<style scoped>
.usage-actions{display:flex;align-items:center;gap:10px}.usage-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.share-cell{display:flex;align-items:center;gap:18px}.share-cell>span{min-width:55px}.share-cell meter{width:130px;height:7px;border:0;border-radius:3px;appearance:none;background:var(--surface)}.share-cell meter::-webkit-meter-bar{background:var(--surface);border:0}.share-cell meter::-webkit-meter-optimum-value{background:var(--primary);border-radius:3px}.share-cell meter::-moz-meter-bar{background:var(--primary);border-radius:3px}.usage-note{display:flex;align-items:flex-start;gap:7px;font-size:12px;color:var(--muted);line-height:1.8;margin:20px 0 0}.usage-note svg{margin-top:3px;flex-shrink:0}@media(max-width:1050px){.usage-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.usage-actions{width:100%}.usage-stats{gap:10px}.share-cell meter{width:75px}}
</style>

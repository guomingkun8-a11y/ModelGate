<script setup lang="ts">
import { computed,ref } from 'vue'
import type { TrendPoint } from '../types'
const props=defineProps<{series:TrendPoint[]}>()
const active=ref<number|null>(null)
const max=computed(()=>Math.max(4,...props.series.map(p=>p.requests)))
const x=(i:number)=>50+i*(710/Math.max(1,props.series.length-1))
const y=(value:number)=>180-(value/max.value)*144
const line=computed(()=>props.series.map((p,i)=>`${i?'L':'M'}${x(i)},${y(p.requests)}`).join(' '))
const area=computed(()=>props.series.length?`${line.value} L${x(props.series.length-1)},180 L50,180 Z`:'')
const ticks=computed(()=>[max.value,Math.round(max.value*.75),Math.round(max.value*.5),Math.round(max.value*.25),0])
const localTime=(point:TrendPoint)=>new Date(point.time).toLocaleTimeString('zh-CN',{hour12:false,hour:'2-digit',minute:'2-digit'})
const labels=computed(()=>props.series.map((p,i)=>({label:localTime(p),i})).filter((_,i)=>i===0||i===props.series.length-1||i%Math.max(1,Math.floor(props.series.length/5))===0))
</script>
<template><div class="trend-chart"><svg viewBox="0 0 800 225" role="img" aria-label="当前时间范围的请求量趋势"><defs><linearGradient id="request-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="var(--primary)" stop-opacity="0.15"/><stop offset="100%" stop-color="var(--primary)" stop-opacity="0.01"/></linearGradient></defs><g v-for="tick in ticks" :key="tick"><line x1="50" x2="760" :y1="y(tick)" :y2="y(tick)" stroke="var(--border)" stroke-dasharray="3 5"/><text x="34" :y="y(tick)+4" text-anchor="end" class="chart-label">{{tick}}</text></g><path :d="area" fill="url(#request-area)"/><path :d="line" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><g v-for="(point,i) in series" :key="i" @mouseenter="active=i" @mouseleave="active=null"><circle :cx="x(i)" :cy="y(point.requests)" r="12" fill="transparent"/><circle v-if="active===i" :cx="x(i)" :cy="y(point.requests)" r="4" fill="var(--primary)"/><title>{{localTime(point)}} · {{point.requests}} 次请求，{{point.errors}} 次失败</title></g><text v-for="label in labels" :key="label.i" :x="x(label.i)" y="211" text-anchor="middle" class="chart-label">{{label.label}}</text></svg><div v-if="!series.length" class="empty-state">当前时间段没有请求，发起一次测试后再来查看。</div></div></template>

<script setup lang="ts">
import { computed } from 'vue'
const props=defineProps<{status:string}>()
const labels:Record<string,string>={healthy:'运行正常',disabled:'已停用',active:'使用中',revoked:'已撤销',success:'成功',error:'失败',running:'处理中'}
const label=computed(()=>labels[props.status]??props.status)
</script>
<template><span class="status-tag" :class="status"><span class="status-dot"></span>{{label}}</span></template>

<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from '../components/AppSidebar.vue'
import AppHeader from '../components/AppHeader.vue'
import DemoRequestPanel from '../components/DemoRequestPanel.vue'
const sidebarOpen=ref(false),testOpen=ref(false)
</script>
<template><div class="admin-shell"><AppSidebar :open="sidebarOpen" @close="sidebarOpen=false"/><div class="main-shell"><AppHeader @menu="sidebarOpen=true" @test="testOpen=true"/><main id="main-content" class="main-content"><RouterView /></main><footer class="app-footer"><span>ModelGate <span class="muted">/</span> 多模型统一网关</span><span>模拟供应商 · 本地数据 · 无外部 API 调用</span></footer></div><DemoRequestPanel v-model="testOpen"/></div></template>

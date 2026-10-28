<script setup lang="ts">
import { Menu,ChevronRight,Play,LogOut,ExternalLink } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
defineEmits<{menu:[];test:[]}>()
const router=useRouter(),auth=useAuthStore()
function logout(){auth.signOut();router.push('/login')}
</script>
<template><header class="app-header"><div class="header-breadcrumb"><button class="icon-btn mobile-menu" aria-label="打开导航" @click="$emit('menu')"><Menu :size="20"/></button><span>工作空间</span><ChevronRight :size="13"/><strong>{{$route.meta.title??'总览'}}</strong></div><div class="header-actions"><span class="environment-badge"><span class="status-dot"></span>演示环境</span><button class="btn btn-secondary header-test" @click="$emit('test')"><Play :size="14"/>测试请求</button><button class="icon-btn" aria-label="退出登录" title="退出登录" @click="logout"><LogOut :size="17"/></button></div></header></template>

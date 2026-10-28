<script setup lang="ts">
import { onMounted,onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
const router=useRouter(),auth=useAuthStore()
function unauthorized(){auth.signOut();router.replace('/login')}
onMounted(()=>window.addEventListener('modelgate:unauthorized',unauthorized))
onUnmounted(()=>window.removeEventListener('modelgate:unauthorized',unauthorized))
</script>
<template><RouterView /></template>

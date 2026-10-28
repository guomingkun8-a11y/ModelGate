<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Layers3,ArrowRight,ShieldCheck,Route,Activity } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../api/http'
const router=useRouter(),auth=useAuthStore(),password=ref('modelgate-demo'),loading=ref(false),error=ref('')
async function submit(){error.value='';loading.value=true;try{await auth.signIn(password.value);router.push('/')}catch(e){error.value=errorMessage(e)}finally{loading.value=false}}
</script>
<template><div class="login-page"><div class="login-brand"><Layers3 :size="25"/>ModelGate</div><section class="login-copy"><span class="environment-badge">本地演示版</span><h1>管理模型流量，<br>从这里开始。</h1><p>一个入口连接多个模型，让每次调用<br class="desktop-only">都有清晰的路径。</p><div class="login-capabilities"><span><Route :size="18"/>智能路由与故障切换</span><span><Activity :size="18"/>可追溯的请求记录</span><span><ShieldCheck :size="18"/>独立的虚拟密钥</span></div></section><form class="login-form" @submit.prevent="submit"><div class="login-form-logo"><Layers3 :size="26"/></div><h2>进入控制台</h2><p class="muted">使用演示账号，体验完整请求链路。</p><label class="form-label" for="password">管理员密码</label><el-input id="password" v-model="password" type="password" show-password autocomplete="current-password" size="large" placeholder="输入演示密码"/><p class="field-note">默认密码：<code>modelgate-demo</code></p><p v-if="error" class="error-state" role="alert">{{error}}</p><el-button class="login-submit" type="primary" native-type="submit" :loading="loading" size="large">进入演示控制台 <ArrowRight :size="17"/></el-button><p class="login-privacy">演示数据保存在本地，不会调用外部模型。</p></form><footer class="login-footer">ModelGate / Open model infrastructure</footer></div></template>

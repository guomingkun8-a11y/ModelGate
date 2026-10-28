import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login } from '../api/auth'
export const useAuthStore = defineStore('auth',()=>{ const token=ref(sessionStorage.getItem('modelgate-token') ?? ''); const name=ref('Demo Admin'); async function signIn(password:string) { const result=await login(password); token.value=result.token; name.value=result.name; sessionStorage.setItem('modelgate-token',result.token) } function signOut() { token.value=''; sessionStorage.removeItem('modelgate-token') } return {token,name,signIn,signOut} })

<script setup lang="ts">
defineProps<{label:string;value:string|number;unit?:string;description?:string;icon?:unknown}>()
</script>
<template><div class="stat-card"><div class="stat-label">{{label}}<slot name="icon" /></div><div class="stat-value mono">{{value}}<span v-if="unit" class="stat-unit">{{unit}}</span></div><div class="stat-description"><slot>{{description}}</slot></div></div></template>

export interface ProviderModel { public_model:string; upstream_model:string }
export interface Provider { id:string; owner_id:string|null; name:string; kind:string; base_url:string; models:ProviderModel[]; has_api_key:boolean; priority:number; weight:number; enabled:boolean; status:'unknown'|'healthy'|'disabled'; latency_ms:number; success_rate:number; rpm_limit:number; concurrency_limit:number }
export interface PublicProviderModel { public_model:string }
export interface PublicProvider { id:string; name:string; kind:string; models:PublicProviderModel[]; enabled:boolean; status:'unknown'|'healthy'|'disabled' }
export type ProviderRecord = Provider | PublicProvider
export interface ModelRoute { id:string; model:string; name:string; strategy?:string; provider_ids:string[]; enabled:boolean }
export interface VirtualKey { id:string; name:string; prefix:string; created_at:string; last_used_at:string|null; status:'active'|'revoked'; rpm_limit:number; total_requests:number }
export interface Attempt { provider_id:string|null; provider:string; status_code:number|null; latency_ms:number; error:string|null }
export interface RequestRecord { id:string; created_at:string; model:string; provider:string; provider_id:string|null; status:'success'|'error'|'running'; status_code:number; latency_ms:number; input_tokens:number|null; output_tokens:number|null; is_stream:boolean; attempts:Attempt[]; error:string|null }
export interface TrendPoint { time:string; label:string; requests:number; errors:number }
export interface ModelUsage { model:string; requests:number; tokens:number }
export interface OverviewData { requests:number; success_rate:number; p95_latency_ms:number; tokens:number; series:TrendPoint[]; model_usage:ModelUsage[]; recent_requests:RequestRecord[]; providers:ProviderRecord[] }
export interface UsageData { total_requests:number; input_tokens:number; output_tokens:number; total_tokens:number; by_model:ModelUsage[]; series:TrendPoint[] }
export interface PageResult<T> { items:T[]; total:number; page:number; page_size:number }

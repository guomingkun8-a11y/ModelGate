export interface Provider { id:string; name:string; kind:string; base_url:string; models:string[]; priority:number; weight:number; enabled:boolean; status:'healthy'|'disabled'; latency_ms:number; success_rate:number; rpm_limit:number; concurrency_limit:number }
export interface ModelRoute { id:string; model:string; name:string; strategy:string; provider_ids:string[]; enabled:boolean }
export interface VirtualKey { id:string; name:string; prefix:string; created_at:string; last_used_at:string|null; status:'active'|'revoked'; rpm_limit:number; total_requests:number }
export interface Attempt { provider_id:string; provider:string; status_code:number; latency_ms:number; error:string|null }
export interface RequestRecord { id:string; created_at:string; model:string; provider:string; provider_id:string; status:'success'|'error'|'running'; status_code:number; latency_ms:number; input_tokens:number; output_tokens:number; is_stream:boolean; attempts:Attempt[]; is_demo:boolean; error:string|null }
export interface TrendPoint { time:string; label:string; requests:number; errors:number }
export interface ModelUsage { model:string; requests:number; tokens:number }
export interface OverviewData { requests:number; success_rate:number; p95_latency_ms:number; tokens:number; series:TrendPoint[]; model_usage:ModelUsage[]; recent_requests:RequestRecord[]; providers:Provider[]; source:'demo' }
export interface UsageData { total_requests:number; input_tokens:number; output_tokens:number; total_tokens:number; by_model:ModelUsage[]; series:TrendPoint[] }
export interface PageResult<T> { items:T[]; total:number; page:number; page_size:number }

# Demo 实现契约

本文件描述当前 Demo；生产目标继续见 PLAN.md。Demo 用 SQLite 保留本地状态，进程内并发保护和受控模拟上游，不依赖 PostgreSQL、Redis 或真实付费服务。生产级共享限流、预算和高可用不属于本次 Demo。

## 运行与鉴权

后端 `127.0.0.1:8010`，同时托管构建后的前端；开发时前端 Vite `127.0.0.1:5173`。Vite 代理 `/internal`、`/v1` 和 `/healthz` 到后端。

管理台采用 React 19、TypeScript、Vite、Ant Design 和 React Router。管理员登录态由 React Context 管理，保存在当前浏览器会话；API 契约和 SQLite 演示数据不因前端迁移而改变。

Demo 管理员登录 `POST /internal/auth/login`，请求 `{password:"modelgate-demo"}`，返回 `{token,name}`。开发默认密码与令牌只用于本地演示，可用环境变量覆盖。管理接口使用 Bearer token；`/v1` 独立使用 Demo 虚拟 Key `sk-demo-local`。新建虚拟 Key 使用 `sk-` 前缀。

## 管理接口

- `GET /internal/metrics/overview?hours=24`：`{requests,success_rate,p95_latency_ms,tokens,series,model_usage,recent_requests,providers,source:"demo"}`。
- `GET /internal/providers`：`Provider[]`；`PATCH /internal/providers/{id}` 修改 `enabled`。
- `GET /internal/model-routes`：`ModelRoute[]`。
- `GET /internal/virtual-keys`：`VirtualKey[]`；`POST` 请求 `{name,rpm_limit}` 返回 `{key,record}`，明文仅返回一次；`DELETE /{id}` 撤销。
- `GET /internal/requests` 支持 `page,page_size,q,status,model,provider,hours`，返回 `{items,total,page,page_size}`；`GET /{id}` 返回单条记录。
- `GET /internal/usage?hours=24`：`{total_requests,input_tokens,output_tokens,total_tokens,by_model,series}`。
- `GET /internal/settings`：运行模式、存储、限制和启动时间的只读信息。
- `POST /internal/demo/request`：`{model,prompt,simulate_failure:false,stream:false}`，执行模拟网关调用并返回 `{request,answer}`。失败也返回可查看的请求记录与友好错误信息。

## 数据类型

```ts
type Provider = {
  id: string; name: string; kind: string; base_url: string; models: string[];
  priority: number; weight: number; enabled: boolean;
  status: 'healthy' | 'disabled'; latency_ms: number; success_rate: number;
  rpm_limit: number; concurrency_limit: number;
}
type ModelRoute = {
  id: string; model: string; name: string; strategy: string;
  provider_ids: string[]; enabled: boolean;
}
type VirtualKey = {
  id: string; name: string; prefix: string; created_at: string;
  last_used_at: string | null; status: 'active' | 'revoked';
  rpm_limit: number; total_requests: number;
}
type Attempt = {
  provider_id: string; provider: string; status_code: number;
  latency_ms: number; error: string | null;
}
type RequestRecord = {
  id: string; created_at: string; model: string; provider: string;
  provider_id: string; status: 'success' | 'error' | 'running';
  status_code: number; latency_ms: number; input_tokens: number;
  output_tokens: number; is_stream: boolean; attempts: Attempt[];
  is_demo: boolean; error: string | null;
}
```

`series` 为 `{time,label,requests,errors}[]`；`model_usage` 与 `by_model` 为 `{model,requests,tokens}[]`。Token 均为模拟估算，不作真实账单依据。初始历史记录也标记 `is_demo`，新增测试请求真实经过模拟调度并持久化。

## 网关与范围

`GET /v1/models`、`POST /v1/chat/completions` 支持虚拟 Key、JSON 与 SSE。模拟供应商不会访问外部网络。上游关闭后跳过；测试故障选项让第一个选中上游返回 503，从而展示切换。最多尝试 3 个不同上游；流开始后不重试。

前端提供总览、供应商状态开关、模型路由查看、虚拟 Key 创建与撤销、可筛选日志详情、用量、设置，以及全局测试请求面板。页面始终显示演示模式，不伪装生产能力。

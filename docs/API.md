# 接口规划

本文保留正式网关的接口规划；当前 Demo 已实现的具体契约与路径见 [DEMO.md](DEMO.md)。运行 Demo 后可在 `/docs` 查看 FastAPI 实际 OpenAPI 文档，避免把规划当成已完成能力。

## 核心模型接口

| 方法 | 路径 | 用途 | 鉴权 |
| --- | --- | --- | --- |
| POST | `/v1/chat/completions` | JSON / SSE 聊天补全 | 虚拟 API Key |
| GET | `/v1/models` | 列出当前可调用的公开模型名 | 虚拟 API Key |
| GET | `/healthz` | 进程存活检查 | 无 |
| GET | `/readyz` | 必需依赖就绪检查 | 无 |

- 调用鉴权使用 `Authorization: Bearer <virtual-key>`。
- 先兼容文本聊天的必要参数：`model`、`messages`、`stream` 及常见采样 / 输出长度参数；不宣称首版覆盖整个 OpenAI API。
- SSE 增量转发上游有效事件，正常结束使用 `[DONE]`。异常中断不补造成功事件。
- 返回网关生成的 `X-Request-ID`，用于关联请求记录和上游尝试。
- 错误采用 `{ "error": { "message": "...", "type": "...", "code": "..." } }`，过滤内部地址、密钥和供应商敏感信息。

## 首版监控接口

| 方法 | 路径 | 前端用途 |
| --- | --- | --- |
| GET | `/internal/metrics/overview` | Overview 总览 |
| GET | `/internal/upstreams` | 上游状态 |
| GET | `/internal/requests` | RequestLogs 查询 |
| GET | `/internal/requests/{request_id}` | 查看请求及其尝试 |
| GET | `/internal/usage` | Usage 统计 |

内部接口使用独立管理令牌保护；不能使用模型调用的虚拟 Key。聚合 API 和明细 API 在联调前统一时间范围、时区、分页与筛选规则，并生成对应 TypeScript 类型。

## 后续管理接口分类

| 前端文件 | 后端职责 | 阶段 |
| --- | --- | --- |
| `auth.ts` | 管理员登录、当前身份、退出 | 完整管理台 |
| `providers.ts` | 上游供应商及加密凭据管理 | 完整管理台 |
| `modelRoutes.ts` | 公开模型映射、优先级与权重管理 | 完整管理台 |
| `virtualKeys.ts` | 虚拟 Key 创建、查询、撤销 | 完整管理台 |
| `requests.ts` | 请求列表、详情和逐次尝试 | 核心 MVP |
| `usage.ts` | Token 用量与聚合统计 | 核心 MVP |

配置编辑 API 和会话的具体契约，在对应阶段开发前确定。前端不得显示未实现或虚构的可操作功能。

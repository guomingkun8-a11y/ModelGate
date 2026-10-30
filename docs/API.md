# 当前接口与权限

当前后端入口为 `app.prod_main:app`，默认地址 `http://127.0.0.1:8012`；启动方式见[根 README](../README.md)。运行服务的 `/docs` 提供完整 OpenAPI 参数和响应契约。早期 SQLite Demo 接口已移除，[DEMO.md](DEMO.md)仅作历史记录。

## 登录和角色

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/internal/auth/login` | 以 `{identifier,password}` 登录，返回 `{token,name,role}`；`identifier` 为邮箱或管理员账号 |
| POST | `/internal/auth/register` | 以 `{email,name,password}` 公开注册，只创建 `user` 账号并返回会话 |
| POST | `/internal/auth/logout` | 撤销当前登录会话 |

管理台 API 使用 `Authorization: Bearer <session-token>`，与模型调用的虚拟 Key 独立。系统只有 `admin` 和 `user` 两种角色，管理员拥有全局管理权限。

## 渠道和模型

| 方法 | 路径 | 权限和用途 |
| --- | --- | --- |
| GET | `/internal/providers` | 管理员查看完整渠道配置及未发布历史记录；用户只读平台共享渠道的名称、类型、公开模型与状态 |
| POST | `/internal/providers` | 管理员添加共享渠道和模型映射 |
| POST | `/internal/providers/test` | 管理员连接上游并通过 `GET /models` 获取模型 ID |
| PATCH | `/internal/providers/{id}` | 管理员修改共享渠道配置或启停 |
| DELETE | `/internal/providers/{id}` | 管理员删除共享渠道 |
| POST | `/internal/providers/{id}/publish` | 管理员明确发布历史私有渠道为平台共享渠道 |
| GET | `/internal/model-routes` | 读取公开模型到共享渠道的路由；普通用户响应不含内部策略配置 |
| GET | `/internal/playground/providers` | 仅管理员：模型测试的渠道列表 |
| POST | `/internal/playground/chat` | 仅管理员：直接测试选定渠道，不进行自动故障切换 |

普通用户不能新增、测试、编辑、删除或启停上游，也不会收到上游地址、Key 状态、真实模型 ID、优先级或权重。上游 API Key 加密保存，任何列表及编辑 API 均不回传明文。

## 账号数据

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / POST | `/internal/virtual-keys` | 查询 / 创建虚拟 Key；新 Key 明文仅返回一次 |
| DELETE | `/internal/virtual-keys/{id}` | 撤销虚拟 Key |
| GET | `/internal/requests` | 分页查询请求记录 |
| GET | `/internal/requests/{id}` | 请求详情和上游尝试 |
| GET | `/internal/metrics/overview` | 请求量、延迟和用量总览 |
| GET | `/internal/usage` | 用量聚合 |
| GET | `/internal/settings` | 不含密钥的运行配置与当前能力边界 |

虚拟 Key、请求记录和用量按账号隔离；管理员拥有全局查看和管理权限。请求日志不保存提示词正文。

## 模型调用与健康检查

| 方法 | 路径 | 用途 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/v1/models` | 列出平台可调用的公开模型名 | 虚拟 API Key |
| POST | `/v1/chat/completions` | 文本聊天补全，使用 `model`、`messages` 和 `stream` | 虚拟 API Key |
| GET | `/healthz` | 进程存活检查 | 无 |
| GET | `/readyz` | 启动就绪信息，未持续探测数据库连接 | 无 |

调用使用 `Authorization: Bearer <sk-virtual-key>`。模型名取自公开模型列表，实际请求由平台路由到管理员配置的共享渠道。可执行请求模板见 [gateway-request.http](../examples/gateway-request.http)。

`stream: true` 当前是缓冲 SSE：等待完整上游响应后输出一个内容块和 `[DONE]`，尚未实现实时事件转发、首 Token 延迟或流式断连处理。Redis 尚未接入，RPM 和并发状态为进程内实现；分布式限流、并发租约和预算治理仍在规划中。

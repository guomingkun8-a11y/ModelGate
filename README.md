# ModelGate

基于 FastAPI、React 19 和 PostgreSQL 的多模型 API 网关。管理员统一配置共享渠道与公开模型，用户通过个人 `sk-` 密钥调用，并查看自己的请求日志和 Token 用量。

## 当前版本：本地可运行的多模型网关

ModelGate 提供 React 19 + TypeScript 管理台和 FastAPI 后端。后端使用 PostgreSQL 保存账号、虚拟密钥、请求记录，以及由管理员统一维护的共享上游渠道和模型路由，并可转发到 OpenAI 兼容上游。

首页提供公开注册入口。普通用户使用邮箱注册和登录，账号数据相互隔离；管理员和普通用户共用登录页面，管理员账号为 `admin`，本机默认密码为 `admin123456`。系统只有 `admin` 和 `user` 两种角色，管理员拥有管理权限。

- **总览**：查看当前账号的请求量、延迟、Token 和近期请求。
- **上游与模型路由**：管理员添加并测试共享上游，配置公开模型名；普通用户只查看可用渠道和模型，通过自己的虚拟密钥调用。
- **虚拟密钥**：创建 `sk-` 密钥、一次展示明文并撤销。
- **日志与用量**：筛选当前账号的请求并查看用量。
- **兼容接口**：提供 `/v1/models` 和 `/v1/chat/completions`。

生产入口使用 PostgreSQL，启动时会自动运行 Alembic 迁移。首次升级已有数据库前，请先备份。当前共享限流仍为单进程实现，Redis 尚未接入。

## 本地启动（Windows）

需要 Python 3.11+、Node.js 20.19+、npm 和 PostgreSQL。可使用项目提供的 Docker Compose 启动 PostgreSQL；已有 PostgreSQL 时也可配置 `.env` 中的连接地址。

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将命令生成的 Fernet Key 填入 `.env` 的 `MASTER_KEY`。本机管理员默认账号为 `admin` / `admin123456`；部署到共享环境前请修改密码。

在第一个终端启动后端：

```powershell
.\scripts\start-backend.ps1 -SkipInstall
```

在第二个终端启动前端：

```powershell
Set-Location frontend
npm ci
npm run dev
```

打开 [http://127.0.0.1:5175](http://127.0.0.1:5175)。注册页为 [http://127.0.0.1:5175/register](http://127.0.0.1:5175/register)；登录页同时接受用户邮箱或管理员账号。后端默认端口为 `8012`，Vite 默认代理到该地址。

## 项目分类

```text
ModelGate/
├── backend/             # FastAPI、PostgreSQL 持久化、网关逻辑与测试
├── frontend/            # React 19 + TypeScript + Vite + Ant Design 管理台
├── docs/                # 当前 API、历史 Demo 设计、长期架构与阶段清单
├── deploy/nginx/        # Nginx 部署配置预留
├── scripts/             # 本地开发辅助脚本
├── examples/            # 可执行的 HTTP 调用示例
├── loadtests/           # 正式压测阶段预留
└── .github/workflows/   # 后续 CI 预留
```

- [当前接口与权限](docs/API.md)
- [历史 Demo 设计（已移除）](docs/DEMO.md)
- [长期目标与架构](docs/PLAN.md)
- [生产版阶段清单](docs/ROADMAP.md)
- [后端运行与验证](backend/README.md)
- [前端运行与结构](frontend/README.md)
- [网关 HTTP 调用示例](examples/gateway-request.http)

## 当前边界

账号数据、上游配置和请求记录持久化到 PostgreSQL。管理员在渠道管理页统一配置 OpenAI Chat Completions 兼容上游，普通用户查看共享渠道和公开模型，并使用自己的虚拟密钥调用。历史私有渠道需经管理员明确确认后发布为共享渠道。

Redis 尚未接入；共享限流、分布式并发租约、预算治理和可靠计费尚未实现。`stream: true` 当前仅在完整上游响应返回后输出一个 SSE 内容块和 `[DONE]`，属于缓冲输出，不是实时增量转发。上游 API Key 由 `MASTER_KEY` 加密保存，列表和编辑 API 不返回密钥。上游仅允许公网 HTTPS 地址，DNS 解析和实际连接都会拒绝私网目标。

## 验证方式

前端类型检查与生产构建命令：

```powershell
cd frontend
npm run typecheck
npm run build
cd ../backend
../.venv/Scripts/python -m pytest tests -q
```


## 开源许可

本项目使用 [MIT License](LICENSE)。

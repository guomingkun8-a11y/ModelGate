# ModelGate 后端

FastAPI 后端使用 PostgreSQL 保存账号、虚拟密钥、管理员统一配置的共享上游渠道、模型路由和请求记录，并转发到 OpenAI 兼容上游。当前账号角色为 `admin` 和 `user`；公开注册只创建普通用户，管理员与普通用户通过同一登录接口认证。

## 启动

在项目根目录准备环境变量、PostgreSQL 和依赖：

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将生成的 Fernet Key 写入 `.env` 的 `MASTER_KEY`。然后在 `backend/` 目录启动：

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.prod_main:app --host 127.0.0.1 --port 8012
```

API 文档位于 `http://127.0.0.1:8012/docs`。前端需单独启动，详见 [`../frontend/README.md`](../frontend/README.md)。

## 账号与密钥

- 本机管理员账号默认为 `admin`，密码默认为 `admin123456`，可用 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 覆盖。部署到共享环境前必须改为强密码。
- 用户通过前端 `/register` 注册。密码以 scrypt 哈希保存，用户只能查看自己的虚拟 Key、请求记录和用量。
- 管理员使用同一登录页面，角色为 `admin`，拥有跨账号管理权限；系统不另设超级管理员角色。
- 新建虚拟 Key 使用 `sk-` 前缀，明文只返回一次，数据库保存带盐哈希。上游 Key 由 `MASTER_KEY` 加密保存。
- 只有管理员可以添加、测试、修改和删除共享上游；普通用户只读取渠道名称、公开模型和启用状态，并通过自己的 `sk-` 虚拟密钥使用网关渠道。上游只允许公网 HTTPS 地址；域名的 DNS 解析和实际 TCP 连接都会拒绝私网目标。
- 请求记录、虚拟密钥和用量仍按用户隔离。历史私有上游不会自动发布；管理员可在渠道页审核后逐条发布为共享渠道。

## 数据和边界

`DATABASE_URL` 默认指向 Compose 映射到宿主机 `15435` 端口的 PostgreSQL。应用启动时自动运行 Alembic 迁移；升级已有数据库前请先备份。请求日志不保存提示词正文。

当前 RPM 与并发限制为进程内实现，Redis 共享限流、分布式并发租约和预算治理尚未接入。多 worker 部署前需先实现共享限流。`stream: true` 会等待完整上游响应，再输出一个 SSE 内容块和 `[DONE]`；尚未实现上游事件的实时增量转发。

## 验证

从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

PostgreSQL 账号隔离集成测试需要设置独立的 `MODEL_GATE_TEST_DATABASE_URL`，不会自动使用开发库。

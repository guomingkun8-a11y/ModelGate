# ModelGate 管理台

React 19 + TypeScript + Vite + Ant Design 管理台，通过 Axios 访问 FastAPI。管理员和注册用户共用登录页面；普通用户可公开注册，数据由后端按账号隔离。

## 开发运行

先按 [`../backend/README.md`](../backend/README.md) 配置 PostgreSQL 并启动后端，再运行：

```powershell
npm ci
npm run dev
```

打开 `http://127.0.0.1:5175`。注册页为 `http://127.0.0.1:5175/register`，登录页为 `http://127.0.0.1:5175/login`。Vite 会将 `/internal`、`/v1` 和 `/healthz` 请求代理到 `127.0.0.1:8012`。如需自定义后端地址，可设置 `MODELGATE_BACKEND_URL`；如需更换前端端口，可设置 `MODELGATE_FRONTEND_PORT`。

管理员本机默认账号为 `admin` / `admin123456`；部署到共享环境前请修改密码。登录令牌仅保存在当前浏览器会话。

```powershell
npm run typecheck
npm run build
```

## 文件分类

- `src/api/`：认证、供应商、模型路由、模型测试、虚拟 Key、请求、用量和设置 API。
- `src/components/`：侧栏、页头、统计和状态标签等共享组件。
- `src/layouts/`：管理台布局。
- `src/pages/`：首页、登录、注册和管理页面。
- `src/router/`：React Router 路由与登录保护。
- `src/stores/`：基于 React Context 的登录会话。
- `src/types/`：后端 API 类型。
- `src/style.css`：共享样式和响应式布局。
- `src/main.tsx`、`src/App.tsx`：React 入口和应用配置。

模型调用会访问管理员配置的上游服务，可能产生费用。当前限流状态保存在后端进程内。

管理员可在“渠道管理”添加、测试和维护共享渠道，并在“模型测试”验证指定渠道。历史私有渠道标为未发布，需明确确认后发布为平台共享渠道。测试台支持浏览器本地会话、系统提示、温度、最大输出 Token、快捷问题、Markdown 风格代码块、复制/编辑/删除消息和停止等待中的请求；测试请求直接发送到所选上游，不会自动切换到其他供应商。

普通用户只读“可用渠道”和“可用模型”，不显示上游地址、凭据、真实模型 ID 或路由参数，也不能进入管理员模型测试页。用户通过“虚拟密钥”创建自己的 `sk-` 密钥，并使用 `/v1/chat/completions` 经平台渠道调用公开模型。

兼容接口的 `stream: true` 当前采用缓冲 SSE：等待完整上游响应后输出一个内容块和 `[DONE]`，尚未实现实时增量转发。

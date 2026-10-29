# ModelGate 演示控制台

React 19 + TypeScript + Vite + Ant Design 管理台，使用 React Router 管理页面、React Context 管理管理员会话、Axios 统一访问后端，图标采用 Lucide React。默认浅色中文界面，数据全部来自本地 FastAPI Demo；API 不可用时显示连接错误，不使用虚构数据回退。

## 开发运行

先按 `../backend/README.md` 启动后端，再运行：

```powershell
cd D:/ModelGate/frontend
npm ci
npm run dev
```

打开 `http://127.0.0.1:5173`。开发代理把 `/internal`、`/v1`、`/healthz` 转发到 `127.0.0.1:8010`。演示密码预填为 `modelgate-demo`，登录令牌只保存在当前浏览器会话。

```powershell
npm run typecheck
npm run build
```

构建产物在 `dist/`。后端支持直接托管这些文件，通过 `http://127.0.0.1:8010` 可在同一个端口访问控制台和 API。

## 文件分类

- `src/api/`：登录、供应商、路由、虚拟 Key、请求、用量和设置接口；`http.ts` 统一鉴权与错误处理。
- `src/components/`：React 侧栏、页头、统计、状态标签、请求趋势图和测试请求面板。
- `src/layouts/AdminLayout.tsx`：管理台通用布局。
- `src/pages/`：Login、Overview、Providers、ModelRoutes、VirtualKeys、RequestLogs、Usage、Settings，各页面使用 `.tsx`。
- `src/router/index.tsx`：React Router 路由、按页加载和登录保护。
- `src/stores/auth.tsx`：基于 React Context 的管理员会话，登录状态保存在 `sessionStorage`。
- `src/hooks/useData.ts`：共享加载、错误与刷新逻辑。
- `src/types/`：与 Demo 后端对应的 TypeScript 类型。
- `src/style.css`：共享设计变量、布局和响应式样式。
- `src/main.tsx`、`src/App.tsx`：React 入口和应用级配置。

## 可体验功能

- 总览：请求量、成功率、P95、Token、趋势和上游状态；支持时间筛选、刷新、JSON 导出。
- 供应商：即时启用 / 停用模拟上游。
- 模型路由：查看公开模型及对应上游优先级和权重。
- 虚拟密钥：创建、一次性展示明文、复制和撤销。
- 请求日志：搜索、状态筛选、分页和逐次上游尝试详情。
- 用量：时间筛选、Token 统计和模型占比。
- 设置：只读环境信息与 Demo 能力边界。
- 测试请求：选择公开模型、输入消息，可模拟首次上游 503 观察故障切换。

管理界面的请求面板以 JSON 展示结果。SSE 接口可通过 Key 页面的 cURL 示例增加 `"stream":true` 体验。供应商和 Token 均为模拟数据，不接外部付费服务；生产目标继续见 `../docs/PLAN.md`。

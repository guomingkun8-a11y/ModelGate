# ModelGate Demo 后端

已实现 FastAPI、本地 SQLite 持久化、受控模拟供应商、JSON / SSE、优先级加权路由、故障切换、进程内 RPM / 并发限制，以及管理台需要的 API。

## 启动

在项目根目录安装：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
```

然后进入 `backend/` 启动：

```powershell
../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

接口文档位于 `http://127.0.0.1:8010/docs`。前端构建产物存在时，后端会同时托管 `frontend/dist`，浏览器直接访问同一端口。

## 默认演示身份

- 管理台密码：`modelgate-demo`，由 `MODEL_GATE_DEMO_PASSWORD` 覆盖。
- 管理令牌：`mg-admin-local-demo`，由 `MODEL_GATE_ADMIN_TOKEN` 覆盖。
- 模型接口虚拟 Key：`mg-demo-local`，只能调用 `/v1`，不能访问管理接口。
- 通过管理页面新建的 Key 只返回一次明文，数据库保存带盐哈希，可立即撤销。

这些默认身份只用于本机 Demo。模拟供应商不会访问页面中展示的外部 URL，不会产生 API 费用。

## 数据和边界

默认数据库为 `backend/data/modelgate-demo.sqlite3`，也可以设置 `MODEL_GATE_DEMO_DB`。首次启动生成 96 条带 Demo 标记的历史记录；新增测试会经过实际模拟调度并保存。数据库中不保存提示词正文或 API Key 明文。Token 是演示估算，不用于账单。

路由最高优先级数值为 100，同组按权重选择；最多尝试 3 个不同上游。测试面板可以故意让首个上游返回 503，观察切换。关闭全部供应商后返回可追溯的失败记录。

当前是单进程演示，不使用 PostgreSQL、Redis，也未实现生产级共享租约、熔断、预算、管理员会话撤销和真实供应商适配。不要启动多个 worker 来声称共享限流；生产路线见 [PLAN.md](../docs/PLAN.md)。

## 验证

从 `backend/` 运行：

```powershell
../.venv/Scripts/python -m pytest tests -q
```

测试覆盖身份隔离、故障切换、禁用上游、Key 创建与撤销、RPM、SSE、持久化和统计。

# 前端管理端说明

前端位于 `frontend/`，用于管理 XR 测试项目、测试会话、性能分析和演示数据。

## 技术栈

- React 18
- TypeScript
- Vite
- Ant Design
- Recharts
- Zustand

## 启动

不需要 PyCharm npm 插件，直接使用命令行：

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

访问：

```text
http://localhost:5173
```

后端默认地址：

```text
http://localhost:8002/api/v1
```

可通过环境变量覆盖：

```powershell
$env:VITE_API_BASE_URL="http://localhost:8002/api/v1"
npm run dev
```

## 登录

默认演示账号：

```text
admin / Admin123!
```

登录接口使用 `application/x-www-form-urlencoded`，前端已在 `src/api/auth.ts` 中处理。

## 页面能力

| 页面 | 说明 |
| --- | --- |
| 仪表盘 | 展示预测试平台概览和演示指标 |
| 项目管理 | 调用后端真实项目 API，支持创建、编辑、删除；项目用于归类 Unity 上传的测试结果 |
| 测试会话 | 优先读取后端真实测试会话，展示 Unity 自动同步的会话、CPU、开始/结束时间和耗时，失败时展示内置样例 |
| 性能分析 | 优先读取后端完整分析、样本曲线和渲染质量评分，失败时展示内置样例 |

## 本地检查

```powershell
npm run check
npm run lint
npm run build
```

或从项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-tests.ps1
```

构建时 Vite 可能提示主 chunk 大于 500KB，这是优化提示，不是错误。

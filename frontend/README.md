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

### Electron 桌面开发模式（推荐）

日常 UI 使用 Electron 应用窗口呈现，不需要打开外部浏览器：

```bash
cd frontend
npm run desktop:dev
```

该命令会同时启动 Vite 和 Electron，并保留 React 热更新。关闭命令所在终端或按 `Ctrl+C` 会同时停止两者。

Electron 当前仅作为前端运行容器，不负责启动或停止 FastAPI、数据库和 Unity。启动桌面界面前，仍需单独启动后端。

首次安装 Electron 依赖：

```bash
npm install
```

如果 npm 包已安装，但启动时报错 `Electron failed to install correctly`，说明 Electron 可执行文件下载未完成。
在中国大陆网络环境下可使用镜像补充下载：

```bash
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ node node_modules/electron/install.js
```

该命令成功后，`node_modules/electron/path.txt` 与 `node_modules/electron/dist` 应当存在。

### 浏览器辅助调试

需要使用浏览器开发工具时，可以继续使用原有方式：

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1 -Browser
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

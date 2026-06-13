# 本地热重载开发模式启动

## macOS / Linux

### 1. 启动数据库（Docker）

```bash
docker compose up -d postgres redis
```

### 2. 启动后端（终端1）

```bash
cd backend
./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

### 3. 启动 Electron 桌面界面（终端2，推荐）

```bash
cd frontend
npm run desktop:dev
```

命令会启动 Vite 开发服务，并自动在 Electron 应用窗口内打开界面。React 代码修改后仍支持热更新。

首次安装后若提示 `Electron failed to install correctly`，执行：

```bash
cd frontend
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ node node_modules/electron/install.js
```

如需使用浏览器辅助调试：

```bash
cd frontend
npm run dev
```

浏览器访问：**[http://localhost:5173](http://localhost:5173)**

---

## Windows

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

该命令会分别打开后端终端和 Electron 前端终端，并自动显示桌面应用窗口。

如需仅启动浏览器前端：

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1 -Browser
```

## 停止服务

- 后端/Electron 前端：在对应终端按 `Ctrl+C`
- 数据库：`docker compose down`

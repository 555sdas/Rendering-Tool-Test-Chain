# Electron 跨平台桌面客户端技术方案

> 文档用途：规划将现有 React 前端以独立桌面应用形式交付，供后续实施、评审与答辩说明使用。  
> 目标平台：Windows、macOS  
> 编写日期：2026-06-13  
> 状态：**计划实施 Electron 开发模式，安装包与正式发布后置**

---

## 1. 背景与目标

当前 XR 渲染测试平台通过浏览器访问 React 前端。项目后续需要以桌面应用形式呈现：

- 用户通过应用图标启动系统；
- 界面在独立应用窗口内显示，不打开 Chrome、Safari 等外部浏览器；
- Windows 与 macOS 使用同一套前端代码；
- 保留现有 React 页面、交互、图表和实时进度能力；
- 不提前绑定后端和数据库的部署方式；
- 后端未来可以部署在本机、局域网服务器或云端。

本方案采用 **Electron 封装现有 React 前端**。Electron 负责桌面窗口、应用生命周期和运行时配置，
React 继续负责全部业务界面，FastAPI 继续通过 HTTP/WebSocket 提供服务。

当前阶段计划引入 Electron 开发模式，让日常启动直接打开独立应用窗口，不再以外部浏览器作为主要操作入口。
React 仍由 Vite 提供开发服务和热更新，后端、数据库和 Unity 的运行方式保持不变。

当前阶段不制作 Windows/macOS 安装包，不实施签名、公证或自动更新。正式安装包和发布能力在后续阶段完成。

---

## 2. 方案结论

推荐采用以下架构：

```text
Electron Desktop Client
├── Main Process
│   ├── 创建和管理应用窗口
│   ├── 读取、校验并保存运行时配置
│   ├── 控制外部链接、单实例和应用生命周期
│   └── 后续可扩展自动更新、托盘和系统通知
├── Preload
│   └── 向 React 暴露最小化、类型安全的桌面能力
└── Renderer
    └── 现有 React + TypeScript + Vite + Ant Design 前端
          │
          ├── HTTP API
          └── WebSocket
                ↓
        可配置的 FastAPI 服务
        ├── 本机后端
        ├── 局域网后端
        └── 云端后端
```

生产版 Electron **加载安装包内的 React 构建产物**，而不是打开远程管理网页。它在用户体验上是独立桌面应用，
不显示浏览器地址栏、标签页和浏览器菜单。

首期桌面客户端只封装前端，不捆绑、启动或停止 FastAPI、数据库和 Unity。后端部署方式确定后，再决定是否增加本地服务管理能力。

### 2.1 当前阶段决策：先切换开发入口，暂不打包

```text
改造前：
启动 Vite → 浏览器访问 http://localhost:5173

当前阶段改造后：
启动 Vite → Electron 自动打开应用窗口 → 应用内加载 http://localhost:5173

未来发布：
启动已安装应用 → Electron 应用窗口 → 加载本地 React 构建产物
```

当前阶段 Electron 只是开发运行容器：

```text
Electron Main Process
→ 创建桌面应用窗口
→ 加载 Vite 开发地址
→ React 保持热更新
→ React 连接现有 FastAPI
```

当前阶段需要实现：

1. 新增最小 Electron Main Process；
2. 新增安全的 Preload 基础文件；
3. 增加 `desktop:dev` 启动命令；
4. 自动等待 Vite 启动后打开应用窗口；
5. 保留 Vite 热更新和前端调试能力；
6. 保留原有 `npm run dev` 浏览器调试入口；
7. 不修改后端、数据库与 Unity 运行方式；
8. 不制作桌面安装包。

---

## 3. 范围定义

### 3.1 当前阶段包含：Electron 开发模式

1. Electron 独立桌面开发窗口。
2. Electron 窗口加载现有 Vite React 前端。
3. React 热更新与 DevTools 调试。
4. Windows 与 macOS 开发环境兼容。
5. 保留原浏览器开发入口作为辅助调试方式。
6. Electron 安全基础配置。
7. 应用窗口标题、尺寸、图标和基本生命周期。

### 3.2 当前阶段不包含

1. 不安装或配置 `electron-builder`。
2. 不制作 `.dmg`、`.exe` 或其他安装包。
3. 不实施签名、公证、自动更新和发布 CI。
4. 不加载本地 React `dist` 作为正式发布入口。
5. 不修改 React 路由以适配 `app://` 正式协议。
6. 不在 Electron 内打包或启动 FastAPI。
7. 不改变后端、数据库和 Unity 的运行方式。

### 3.3 未来桌面化阶段包含

1. Electron 独立桌面窗口。
2. 复用现有全部 React 页面和业务功能。
3. 支持 Windows 与 macOS 打包。
4. 支持运行时配置 FastAPI 服务地址。
5. HTTP API 与 WebSocket 根据同一个服务地址连接。
6. 应用内保存服务地址和窗口状态。
7. 后端不可用时展示桌面客户端连接诊断页。
8. 保留现有网页版开发、构建和部署方式。
9. Electron 安全基线、打包配置和基础 CI。

### 3.4 未来桌面化首期不包含

1. 不在 Electron 内打包 Python/FastAPI。
2. 不在 Electron 内安装或管理 PostgreSQL、SQLite、Redis、Docker。
3. 不由 Electron 直接启动或停止 Unity。
4. 不实现自动更新服务端。
5. 不实现离线业务模式。
6. 不重写 React 页面为原生 Swift、C# 或 Flutter UI。

### 3.5 后续可扩展

- 本机 FastAPI 服务发现与一键启动；
- Unity 进程与测试状态的系统级通知；
- 托盘常驻与后台运行；
- 自动更新；
- 系统钥匙串保存登录凭据；
- 文件选择器、日志目录打开和本地诊断包导出。

---

## 4. 为什么选择 Electron

| 维度 | Electron | Tauri | Flutter / 原生重写 |
| --- | --- | --- | --- |
| 复用现有 React 前端 | 完整复用 | 完整复用 | 基本不能复用 |
| Windows/macOS 渲染一致性 | 高，统一 Chromium | 依赖系统 WebView | 高 |
| 实施成本 | 低 | 中 | 高 |
| 前端团队学习成本 | 低 | 需要 Rust/桌面能力学习 | 需要重写 UI |
| 安装包和内存 | 较大 | 较小 | 视方案而定 |
| 生态与调试工具 | 成熟 | 较成熟 | 成熟但改造量大 |

本项目包含复杂表格、图表、实时监控、WebSocket 和大量现有 React 页面。相比重新开发原生 UI，
Electron 能以最低风险满足“应用内呈现”和双平台交付要求。

Electron 内部使用 Web 技术渲染，但交付形态是桌面应用。VS Code、Slack、Discord 等应用采用相同技术路线。

---

## 5. 关键设计原则

### 5.1 桌面版是新的前端发布渠道

桌面版与网页版共享 React 源码和业务组件：

```text
同一套 React 源码
├── Web 构建：部署到浏览器访问地址
└── Electron 构建：打包到 Windows/macOS 应用
```

禁止为 Electron 复制一套独立业务页面，否则后续功能会产生双份维护成本。

### 5.2 后端地址必须运行时可配置

当前前端主要依赖构建时环境变量：

```text
VITE_API_BASE_URL
```

这不适合桌面应用。应用打包后，用户应能在不重新构建客户端的情况下切换：

```text
http://127.0.0.1:8002/api/v1
http://192.168.1.20:8002/api/v1
https://api.example.com/api/v1
```

推荐引入统一运行时配置服务：

```typescript
interface DesktopRuntimeConfig {
  apiBaseUrl: string;
}
```

读取优先级：

```text
Electron 用户配置
→ Web 构建时 VITE_API_BASE_URL
→ 默认 /api/v1
```

### 5.3 HTTP 与 WebSocket 必须共享服务配置

当前 `apiClient` 使用 `VITE_API_BASE_URL`，Unity 进度 WebSocket 根据 `window.location.origin` 生成。

Electron 生产环境加载本地资源后，页面来源可能是：

```text
app://xr-test-platform
```

此时不能继续根据 `window.location.origin` 推导后端地址。应统一通过运行时 API 地址生成：

```text
http://host/api/v1  → ws://host/api/v1
https://host/api/v1 → wss://host/api/v1
```

所有 API、WebSocket、登录刷新和健康检查必须使用同一配置源。

### 5.4 Renderer 不直接获得 Node.js 权限

Electron 必须启用以下安全设置：

```typescript
new BrowserWindow({
  webPreferences: {
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true,
    preload: preloadPath,
  },
});
```

React Renderer 不能直接访问 `fs`、`child_process`、系统环境变量等能力。需要桌面能力时，通过 Preload
暴露窄接口，并在 Main Process 中校验输入。

---

## 6. 推荐目录结构

当前开发模式建议先在 `frontend` 内增加轻量 Electron 目录，减少初期工程复杂度；正式发布前再根据需要拆分独立
`desktop` 包：

```text
Rendering-Tool-Test-Chain-main/
├── backend/
├── frontend/
│   ├── electron/
│   │   ├── main.cjs
│   │   └── preload.cjs
│   ├── src/
│   └── dist/
└── docs/problems/electron-desktop-client-plan.md
```

当前开发模式只需要：

```text
并行启动 Vite 与 Electron
→ Electron 等待 http://localhost:5173 可用
→ 创建窗口并加载 Vite
```

正式发布阶段再引入 `desktop` 独立包、TypeScript Main/Preload 构建和 `electron-builder`。

---

## 7. Electron 进程职责

### 7.1 Main Process

负责：

- 确保应用单实例运行；
- 创建主窗口并恢复窗口大小；
- 开发环境加载 Vite；
- 生产环境加载本地 React 资源；
- 保存和读取服务地址；
- 限制窗口导航；
- 使用系统默认浏览器打开明确允许的外部链接；
- 提供后端连接诊断；
- 处理应用退出与崩溃日志。

当前开发模式只实现其中最小集合：

- 创建单个应用窗口；
- 加载 `http://localhost:5173`；
- Vite 页面加载失败时自动重试；
- macOS 点击 Dock 图标时重新创建窗口；
- 所有窗口关闭时按平台规则退出；
- 默认打开 DevTools；
- 禁止页面在当前窗口导航到外部地址。

当前开发模式不负责：

- 启动后端；
- 操作数据库；
- 直接管理 Unity；
- 读取生产运行时配置；
- 自动更新；
- 安装包生命周期。

### 7.2 Preload

当前开发模式可先提供空的安全 Preload，确认 Renderer 与 Node.js 隔离：

```javascript
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('desktop', {
  isElectron: true,
});
```

未来需要桌面能力时，再扩展为：

```typescript
interface DesktopBridge {
  getRuntimeConfig(): Promise<DesktopRuntimeConfig>;
  updateRuntimeConfig(config: DesktopRuntimeConfig): Promise<DesktopRuntimeConfig>;
  getAppInfo(): Promise<{ version: string; platform: string }>;
  openExternal(url: string): Promise<void>;
}
```

Preload 不暴露通用 IPC、任意文件读取、Shell 命令执行等高风险能力。

### 7.3 Renderer

继续运行现有 React 应用，仅增加：

- 当前：Electron 环境识别与桌面桥接类型声明；
- 未来：运行时 API 配置读取；
- 未来：服务连接设置和诊断 UI；
- 未来：Electron 正式发布路由适配。

---

## 7.4 当前开发模式最小实现

### 7.4.1 依赖

当前只需要开发依赖：

```bash
cd frontend
npm install --save-dev electron concurrently wait-on
```

说明：

- `electron`：提供桌面应用运行环境；
- `concurrently`：并行启动 Vite 与 Electron；
- `wait-on`：等待 Vite 地址可访问后再创建 Electron 窗口。

当前不安装：

```text
electron-builder
electron-updater
签名与发布相关依赖
```

### 7.4.2 `package.json` 脚本

建议在 `frontend/package.json` 增加：

```json
{
  "main": "electron/main.cjs",
  "scripts": {
    "dev": "vite",
    "desktop:dev": "concurrently -k \"npm run dev\" \"npm run desktop:open\"",
    "desktop:open": "wait-on http://localhost:5173 && electron ."
  }
}
```

使用方式：

```bash
# 日常应用内开发入口
npm run desktop:dev

# 保留的浏览器辅助调试入口
npm run dev
```

### 7.4.3 最小 Main Process

`frontend/electron/main.cjs`：

```javascript
const { app, BrowserWindow, shell } = require('electron');
const path = require('node:path');

const DEV_URL = 'http://localhost:5173';

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 720,
    title: 'XR 测试平台',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  window.loadURL(DEV_URL);
  window.webContents.openDevTools({ mode: 'detach' });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
```

### 7.4.4 最小 Preload

`frontend/electron/preload.cjs`：

```javascript
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('desktop', {
  isElectron: true,
  platform: process.platform,
});
```

### 7.4.5 类型声明

建议增加 `frontend/src/types/desktop.d.ts`：

```typescript
export {};

declare global {
  interface Window {
    desktop?: {
      isElectron: boolean;
      platform: string;
    };
  }
}
```

业务组件不应依赖 `window.desktop` 才能运行。该对象用于未来按需增加桌面体验，网页版缺少它时仍须正常工作。

### 7.4.6 当前开发启动顺序

```text
npm run desktop:dev
    │
    ├─ concurrently 启动 npm run dev
    │      └─ Vite 监听 http://localhost:5173
    │
    └─ concurrently 启动 npm run desktop:open
           └─ wait-on 等待 Vite 可用
                  └─ electron .
                         └─ 独立应用窗口加载 React 页面
```

用户日常只需要执行一个命令，不需要手动打开浏览器。

### 7.4.7 当前阶段退出行为

- 关闭 Electron 窗口仅关闭 UI；
- `concurrently -k` 会结束 Vite 与 Electron 开发进程；
- 不自动关闭 FastAPI、数据库或 Unity；
- 测试进行时关闭 Electron 后，后端和 Unity 测试仍可继续；
- 重新执行 `npm run desktop:dev` 后，可通过已有活动任务恢复机制重新显示进度。

---

## 8. 前端改造设计

### 8.1 API Client

当前：

```typescript
axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
});
```

建议改造为可重新配置的客户端：

```typescript
export function setApiBaseUrl(apiBaseUrl: string): void {
  apiClient.defaults.baseURL = apiBaseUrl;
}
```

应用启动流程：

```text
读取运行时配置
→ 校验 URL
→ 设置 Axios baseURL
→ 初始化 React 应用
→ 请求 /health 或 /auth/me
```

Token 刷新请求也必须使用当前运行时地址，不能继续引用固定常量。

### 8.2 WebSocket

增加统一工具：

```typescript
function toWebSocketBaseUrl(apiBaseUrl: string): string
```

并替换所有根据 `window.location.origin` 构造 WebSocket 的逻辑。

### 8.3 路由

当前使用 `BrowserRouter`。Electron 生产环境若直接通过 `file://` 加载，刷新子路由可能失败。

推荐使用 Electron 自定义协议：

```text
app://xr-test-platform/
```

Main Process 将所有应用内路由回退到 React `index.html`，从而继续使用 `BrowserRouter`，并保持网页版 URL
结构不变。

低成本备选方案是桌面版使用 `HashRouter`，但会产生 `#/projects/1` URL，且需要维护 Web/Electron 路由差异，
不作为首选。

### 8.4 设置页

桌面环境下在系统设置页新增“客户端连接”区域：

- 当前服务地址；
- 修改服务地址；
- 测试连接；
- 服务状态和响应时间；
- 恢复默认地址；
- 应用版本与平台。

切换服务地址时应：

1. 校验协议仅允许 `http` / `https`；
2. 重新初始化 API Client；
3. 清除旧服务的登录 Token，避免跨服务复用凭据；
4. 重新跳转登录页。

### 8.5 登录状态

首期可继续使用 `localStorage` 保存 JWT，与网页版保持一致。

后续正式发布可使用系统钥匙串：

- macOS Keychain；
- Windows Credential Manager；
- Electron `safeStorage` 或受维护的钥匙串库。

---

## 9. 后端兼容要求

Electron 首期不改变 FastAPI 业务接口，但后端需要兼容桌面客户端来源。

### 9.1 CORS

如果桌面客户端使用自定义 `app://` 协议，需验证 Electron 请求的 Origin，并在后端 CORS 配置中加入明确允许项。
不应简单使用任意 Origin 与凭据组合。

### 9.2 HTTPS/WSS

连接云端后端时必须使用：

```text
HTTPS + WSS
```

避免 JWT、设备令牌和测试数据通过明文网络传输。

### 9.3 服务能力探测

建议增加稳定的公开健康检查和版本信息：

```http
GET /health
GET /api/v1/system-info
```

桌面客户端连接时检查：

- 服务是否可达；
- API 版本是否兼容；
- 是否需要登录；
- WebSocket 是否可连接。

---

## 10. 安全设计

### 10.1 Electron 安全基线

- `contextIsolation: true`
- `nodeIntegration: false`
- `sandbox: true`
- 禁止任意 `window.open`
- 禁止 Renderer 导航到非应用地址
- 外部链接必须经过白名单校验后交给系统浏览器
- IPC 使用固定频道和结构化参数
- 不在 Renderer 暴露文件系统、Shell 或进程执行能力
- 生产包不开放 DevTools 快捷入口

### 10.2 内容安全策略

生产环境设置严格 CSP，至少限制：

```text
default-src 'self'
script-src 'self'
style-src 'self' 'unsafe-inline'
connect-src 'self' <configured-api-host> ws: wss:
img-src 'self' data:
```

由于服务地址可以运行时修改，CSP 与连接白名单需要由 Main Process 或自定义协议响应动态生成。

### 10.3 配置安全

- 服务地址只接受合法 HTTP/HTTPS URL；
- 禁止 `javascript:`、`file:` 等协议；
- 配置写入 Electron `userData` 目录；
- 不在配置文件中保存密码、设备令牌或数据库凭据；
- 切换后端时清理旧登录状态。

---

## 11. Windows 与 macOS 打包

推荐使用 `electron-builder` 生成安装包。

### 11.1 macOS

输出：

```text
.dmg
.zip
```

开发和校内演示阶段可先使用未签名包，但首次打开会出现系统安全提示。

正式分发需要：

- Apple Developer ID；
- Hardened Runtime；
- 应用签名；
- Notarization 公证；
- `.icns` 图标；
- Intel 与 Apple Silicon 架构策略。

推荐首期生成：

```text
arm64
x64
```

是否制作 universal 包根据安装包体积和分发方式决定。

### 11.2 Windows

输出：

```text
NSIS .exe 安装程序
portable .exe（可选）
```

正式分发建议配置代码签名证书，减少 SmartScreen 警告。需要准备 `.ico` 图标，并分别验证 Windows 10、Windows 11。

### 11.3 构建平台限制

建议：

- macOS 安装包在 macOS 构建；
- Windows 安装包在 Windows 构建；
- 使用 GitHub Actions 或其他 CI 分平台执行。

不应依赖单台 macOS 机器稳定生成完整 Windows 发布包，反之亦然。

---

## 12. 推荐依赖与脚本

桌面包建议依赖：

```text
electron
electron-builder
typescript
vite（可选，用于 Main/Preload 构建）
electron-store（可选，用于非敏感配置）
```

建议脚本：

```json
{
  "scripts": {
    "dev": "启动 React Vite 与 Electron",
    "build:renderer": "构建 frontend",
    "build:desktop": "构建 Electron Main/Preload",
    "package": "构建当前平台安装包",
    "package:mac": "构建 macOS 安装包",
    "package:win": "构建 Windows 安装包",
    "check": "TypeScript + ESLint + Electron 配置校验"
  }
}
```

---

## 13. 开发与生产运行流程

### 13.1 开发环境

```text
启动 FastAPI（本机或远端）
→ 启动 Vite http://localhost:5173
→ 启动 Electron
→ Electron 加载 Vite 页面
→ React 根据运行时配置连接 FastAPI
```

开发环境允许打开 DevTools 和热更新。

### 13.2 生产环境

```text
用户启动桌面应用
→ Main Process 注册 app:// 协议
→ 加载安装包内 React dist
→ 读取 userData 中的服务地址
→ Renderer 初始化 API Client
→ 检查后端服务
→ 登录并进入应用
```

如果后端不可达，显示连接诊断页，而不是白屏或持续报网络错误。

---

## 14. 分阶段实施计划

### 当前阶段：实施 Electron 开发模式

- [x] 确定采用 Electron 作为应用内 UI 容器；
- [x] 明确 Electron 仅负责前端呈现，不绑定后端与数据库部署；
- [ ] 安装 `electron`、`concurrently`、`wait-on` 开发依赖；
- [ ] 新增 `frontend/electron/main.cjs`；
- [ ] 新增 `frontend/electron/preload.cjs`；
- [ ] 新增 `desktop:dev` 与 `desktop:open` 脚本；
- [ ] 日常开发改为应用窗口内操作；
- [ ] 保留原浏览器开发入口；
- [ ] 验证 Windows 与 macOS Electron 开发模式；
- [ ] 继续保持 API、WebSocket 和业务组件可复用。

当前阶段验收：

- 执行 `npm run desktop:dev` 后自动打开 Electron 应用窗口；
- 不需要手动打开外部浏览器；
- Electron 窗口内可以登录、切换页面、启动测试和查看实时进度；
- React 修改后 Electron 窗口内能够热更新；
- 关闭并重新打开 Electron 后，可以恢复后端正在进行的测试；
- 网页版仍可通过 `npm run dev` 正常开发；
- 不生成桌面安装包；
- 后端、数据库和 Unity 启动方式保持不变。

### 后续阶段 0：前置整理

- [ ] 抽离统一运行时 API 配置；
- [ ] HTTP、Token 刷新、WebSocket 使用同一服务地址；
- [ ] 保持网页版功能和构建通过；
- [ ] 增加后端连接诊断能力。

验收：

- 网页版行为不变；
- 修改运行时服务地址后，HTTP 与 WebSocket 都连接到新地址。

### 后续阶段 1：Electron 生产模式

- [ ] 根据规模决定是否拆分独立 `desktop` 包；
- [ ] 将 Main/Preload 改为 TypeScript 并增加测试；
- [ ] 生产环境加载本地 React 构建产物；
- [ ] 注册 `app://` 协议并处理 SPA 路由；
- [ ] 禁止外部导航；
- [ ] 关闭生产 DevTools。

验收：

- 双击应用图标后打开独立窗口；
- 不打开外部浏览器；
- 可以登录、切换页面、查看图表和实时进度。

### 后续阶段 2：运行时连接配置

- [ ] 增加服务地址设置；
- [ ] 增加连接测试与错误页；
- [ ] 切换服务时清理旧登录状态；
- [ ] 支持本机、局域网和云端服务地址。

验收：

- 不重新打包即可切换后端；
- 后端不可用时给出可理解的诊断信息；
- 恢复连接后可以正常登录。

### 后续阶段 3：打包与发布

- [ ] 配置 `electron-builder`；
- [ ] 准备 Windows/macOS 图标；
- [ ] 生成 `.dmg` 与 Windows 安装程序；
- [ ] 建立双平台 CI；
- [ ] 记录版本号、构建号与发布说明。

验收：

- Windows 10/11 安装并运行；
- macOS Intel/Apple Silicon 安装并运行；
- 安装、升级、卸载不会破坏用户配置。

### 后续阶段 4：正式分发增强

- [ ] macOS 签名与公证；
- [ ] Windows 代码签名；
- [ ] 自动更新；
- [ ] 系统钥匙串；
- [ ] 崩溃日志和诊断包导出。

---

## 15. 测试方案

### 15.1 功能测试

- 登录、刷新令牌和退出；
- 项目、测试配置、单场景和多场景页面；
- HTTP API 请求；
- WebSocket 实时进度与重连；
- 页面刷新和路由跳转；
- 全局测试进度条；
- 文件下载、报告导出和外部链接；
- 服务地址切换与连接失败处理。

### 15.2 桌面专项测试

- 单实例启动；
- 窗口大小与位置恢复；
- 应用关闭和重新打开；
- 无网络启动；
- 后端运行中断与恢复；
- 禁止外部页面在应用窗口内导航；
- Renderer 无法直接访问 Node.js；
- 安装、升级和卸载；
- Windows/macOS 高分屏显示。

### 15.3 回归要求

每次桌面版本发布前执行：

```text
后端 pytest
前端 TypeScript check
前端 ESLint
前端 Vite production build
Electron Main/Preload TypeScript check
Electron 安全配置检查
Windows/macOS 冒烟测试
```

---

## 16. 风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| API 地址仍散落在前端代码中 | 切换后端后部分功能失效 | 先完成统一运行时配置，再引入 Electron |
| WebSocket 根据页面 Origin 构造 | Electron 本地协议下无法连接 | 统一由 API 地址转换 |
| BrowserRouter 在本地资源刷新失败 | 子页面刷新白屏 | 使用 `app://` 自定义协议和 SPA fallback |
| Electron Renderer 获得 Node 权限 | 本地安全风险 | context isolation、sandbox、窄 Preload API |
| 云端后端 CORS/HTTPS 未配置 | 桌面版无法连接或不安全 | 明确 Origin、HTTPS/WSS、连接诊断 |
| Windows/macOS 打包表现不同 | 双平台发布不稳定 | 分平台 CI 和真实设备验收 |
| 未签名安装包被系统拦截 | 用户无法顺利安装 | 演示版提供说明，正式版完成签名与公证 |
| Electron 包体积较大 | 下载与安装成本增加 | 接受首期成本，按需优化资源和 sourcemap |
| 后端未来本地化需求变化 | Electron 架构返工 | 首期保持前端容器边界，后续单独增加服务管理模块 |

---

## 17. 验收标准

当前 Electron 开发模式满足以下条件即可验收：

1. Windows 和 macOS 开发环境均能运行 Electron。
2. 执行一个命令即可打开独立应用窗口。
3. 日常使用不需要打开外部浏览器。
4. Electron 窗口加载 Vite React 页面并支持热更新。
5. 现有主要业务页面与浏览器运行效果一致。
6. HTTP API、登录刷新和 WebSocket 能正常连接现有后端。
7. Renderer 未启用 Node.js 集成。
8. 关闭 Electron 不会意外停止后端、数据库或 Unity。
9. 网页版仍可独立开发和构建。
10. 前端检查、生产构建和双平台 Electron 开发模式冒烟测试通过。

未来正式发布阶段再追加以下验收：

1. Windows 和 macOS 均可通过安装包安装并启动。
2. 生产应用加载本地打包的 React 资源。
3. 用户可以运行时切换本机、局域网或云端后端。
4. 后端不可用时显示连接诊断。
5. 完成签名、公证与发布流程。

---

## 18. 答辩与对外表述建议

可将最终交付形态描述为：

> 系统采用 Electron 构建 Windows 与 macOS 跨平台桌面客户端。客户端在独立应用窗口内运行并加载本地打包的
> React 界面，不依赖外部浏览器。业务服务通过可配置 API 地址连接，因此后端和数据库可以根据部署需求运行在
> 本机、局域网服务器或云端，不影响桌面客户端的交付与使用。

该表述准确说明了应用内呈现方式，同时保留后端部署演进空间。

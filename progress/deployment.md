# 部署与本地运行说明

最后更新：2026-05-30

## 本地开发推荐方式

不依赖 PyCharm npm 插件，使用 PowerShell 脚本启动。

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\seed-demo-data.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

访问：

```text
前端：http://localhost:5173
后端：http://localhost:8002/api/v1/docs
```

## 单独启动

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

## 数据库

本地默认使用：

```text
backend/xr_test.db
```

环境变量：

```text
DATABASE_URL=sqlite:///./xr_test.db
SECRET_KEY=test-secret-key-for-local-dev-only
```

生产或 Docker 环境可切换 PostgreSQL：

```text
postgresql://xruser:xrpass@localhost:5432/xr_test_db
```

## Docker Compose

项目仍保留 Docker Compose 配置，包含 PostgreSQL、Redis、后端、前端和 Nginx。当前本机验证优先使用本地 SQLite + 脚本方式。

```powershell
docker compose up -d
docker compose logs -f
docker compose down
```

## 本地验证

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-tests.ps1
```

包含：

- 后端 pytest
- 前端 TypeScript 检查
- 前端 ESLint
- 前端生产构建

## 备份与恢复

PostgreSQL Docker 部署可使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\restore.ps1 -BackupFile .\backups\xxx.sql
```

SQLite 本地开发可直接备份：

```text
backend/xr_test.db
```

## 端口

| 服务 | 端口 |
| --- | --- |
| 后端 FastAPI | 8002 |
| 前端 Vite | 5173 |
| Docker Nginx | 80 |

## 常见问题

- PyCharm 提示 npm 插件禁用：直接用 `scripts/start-frontend.ps1`。
- 登录失败：确认已运行 `scripts/seed-demo-data.ps1`，账号为 `admin / Admin123!`。
- 前端请求失败：确认后端在 `8002` 端口运行。
- Unity 未生成结果：使用 `scripts/run-boatattack-editmode.ps1`，不要手动加 `-quit`。

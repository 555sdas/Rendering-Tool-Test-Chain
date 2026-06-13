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

### 3. 启动前端（终端2）

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

## 停止服务

- 后端/前端：在对应终端按 `Ctrl+C`
- 数据库：`docker compose down`

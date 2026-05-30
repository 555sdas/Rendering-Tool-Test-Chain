# 前端接口与页面说明

最后更新：2026-05-30

前端默认读取：

```text
http://localhost:8002/api/v1
```

配置位置：

```text
frontend/src/api/client.ts
```

## API 模块

| 文件 | 说明 |
| --- | --- |
| `src/api/auth.ts` | 登录、登出、刷新令牌、当前用户 |
| `src/api/projects.ts` | 项目列表、创建、更新、删除 |
| `src/api/sessions.ts` | 测试会话、样本、统计 |
| `src/api/analysis.ts` | FPS、帧时间、内存、完整分析、趋势、渲染质量评分 |

## 登录格式

后端使用 OAuth2 表单登录，前端必须发送：

```text
Content-Type: application/x-www-form-urlencoded
```

默认账号：

```text
admin / Admin123!
```

## 页面进度

| 页面 | 状态 | 说明 |
| --- | --- | --- |
| 登录 | 已完成 | JWT 登录，登录后写入本地状态 |
| 项目管理 | 已接后端 | 支持真实项目 CRUD |
| 测试会话 | 已接后端 | 优先读取真实会话，后端不可用时显示内置样例 |
| 性能分析 | 已接后端 | 优先读取完整分析、样本曲线和渲染质量评分，后端不可用时显示内置样例 |
| 仪表盘 | 演示态 | 当前为演示统计，后续可接聚合 API |
| 系统设置 | 占位 | 可扩展阈值、报告模板、工具链路径配置 |

## 前端启动

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

## 本地检查

```powershell
cd frontend
npm run check
npm run lint
npm run build
```

当前检查通过。构建存在 Vite chunk 大小提示，属于性能优化建议。

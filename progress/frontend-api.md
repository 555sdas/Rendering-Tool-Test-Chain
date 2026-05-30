# 前端 API 模块操作文档

> 本文档描述前端各 API 模块的功能、类型定义和使用方法。
> 最后更新：2026-05-29
>
> ### 最新更新：登录接口格式说明（`application/x-www-form-urlencoded`）

---

## 一、认证 API (`src/api/auth.ts`)

### 功能
- 用户登录、登出
- Token 刷新
- 获取当前用户信息
- 修改密码

### 类型定义

```typescript
interface UserInfo {
  id: number;
  username: string;
  role: 'admin' | 'tester' | 'report_editor' | 'viewer';
  created_at: string;
}

interface LoginRequest {
  username: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}
```

### 使用方法

```typescript
import { authApi } from '@/api/auth';

// 登录（注意：使用 x-www-form-urlencoded 格式）
const response = await authApi.login({ username: 'admin', password: 'Admin123!' });

// 获取当前用户
const user = await authApi.me();

// 登出
await authApi.logout();
```

### 重要说明

**登录请求格式**：后端使用 `OAuth2PasswordRequestForm`，前端必须发送 `application/x-www-form-urlencoded` 格式的数据，而非 JSON。

正确示例：
```typescript
const params = new URLSearchParams();
params.append('username', credentials.username);
params.append('password', credentials.password);
const response = await apiClient.post('/auth/login', params, {
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
});
```

错误示例（会导致 `[object Object]` 报错）：
```typescript
// 不要这样写！
const response = await apiClient.post('/auth/login', { username, password });
```

---

## 二、项目 API (`src/api/projects.ts`)

### 功能
- 项目列表查询（支持搜索、状态筛选）
- 项目详情获取
- 项目创建、更新、删除

### 类型定义

```typescript
interface Project {
  id: number;
  name: string;
  description: string | null;
  project_type: string;
  status: string;
  created_by: number | null;
  created_at: string;
  updated_at: string | null;
}

interface ProjectCreate {
  name: string;
  description?: string;
  project_type?: string;
  status?: string;
}
```

### 使用方法

```typescript
import { projectsApi } from '@/api/projects';

// 获取项目列表
const projects = await projectsApi.list();

// 搜索项目
const results = await projectsApi.list({ search: 'VR场景' });

// 创建项目
const newProject = await projectsApi.create({
  name: 'VR场景渲染性能测试',
  description: '针对VR大空间场景的渲染性能基准测试',
  project_type: '渲染性能',
  status: 'active',
});

// 更新项目
await projectsApi.update(1, { name: '新名称' });

// 删除项目
await projectsApi.delete(1);
```

---

## 三、测试会话 API (`src/api/sessions.ts`)

### 功能
- 测试会话列表查询
- 测试会话创建、启动、停止
- 性能样本添加和查询
- 会话统计信息获取

### 类型定义

```typescript
interface TestSession {
  id: number;
  name: string;
  description: string | null;
  status: string;
  device_model: string | null;
  os_version: string | null;
  xr_runtime: string | null;
  app_version: string | null;
  scene_id: number | null;
  user_id: number | null;
  project_id: number | null;
  config: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  created_at: string;
}

interface PerformanceSample {
  id: number;
  test_session_id: number;
  timestamp: string;
  frame_time_ms: number | null;
  fps: number | null;
  cpu_usage_percent: number | null;
  gpu_usage_percent: number | null;
  memory_mb: number | null;
  // ... 更多字段
}
```

### 使用方法

```typescript
import { sessionsApi } from '@/api/sessions';

// 创建测试会话
const session = await sessionsApi.create({
  name: 'Quest3渲染测试',
  device_model: 'Meta Quest 3',
  os_version: 'Android 12',
  xr_runtime: 'OpenXR',
  project_id: 1,
});

// 启动会话
await sessionsApi.start(session.id);

// 添加性能样本
await sessionsApi.addSample(session.id, {
  timestamp: new Date().toISOString(),
  fps: 72.5,
  frame_time_ms: 13.8,
  cpu_usage_percent: 45.2,
  gpu_usage_percent: 78.1,
  memory_mb: 2048,
});

// 获取样本列表
const samples = await sessionsApi.getSamples(session.id);

// 停止会话
await sessionsApi.stop(session.id);

// 获取统计信息
const stats = await sessionsApi.getStatistics(session.id);
```

---

## 四、性能分析 API (`src/api/analysis.ts`)

### 功能
- FPS 统计分析
- 帧时间分析
- 内存分析
- 热分析
- 阈值规则检查
- 完整性能报告
- 多会话趋势分析

### 类型定义

```typescript
interface FpsAnalysis {
  count: number;
  mean: number;
  median: number;
  std: number;
  min: number;
  max: number;
  p1: number;
  p5: number;
  p95: number;
  p99: number;
  below_30_count: number;
  below_60_count: number;
  jank_count: number;
}

interface FullReport {
  session_info: {
    id: number;
    name: string;
    status: string;
    device_model: string | null;
    // ...
  };
  fps_analysis: FpsAnalysis;
  frame_time_analysis: FrameTimeAnalysis;
  memory_analysis: MemoryAnalysis;
  thermal_analysis: ThermalAnalysis;
  threshold_violations: ThresholdViolation[];
}
```

### 使用方法

```typescript
import { analysisApi } from '@/api/analysis';

// FPS 分析
const fpsData = await analysisApi.getFpsAnalysis(1);
console.log(`平均FPS: ${fpsData.mean}`);
console.log(`P95 FPS: ${fpsData.p95}`);
console.log(`掉帧次数: ${fpsData.jank_count}`);

// 完整报告
const report = await analysisApi.getFullReport(1);

// 趋势分析
const trend = await analysisApi.getTrendAnalysis([1, 2, 3], 'fps');

// 阈值检查
const violations = await analysisApi.checkThresholds(1, 1);
```

---

## 五、HTTP 客户端配置 (`src/api/client.ts`)

### 功能
- Axios 实例配置
- 请求/响应拦截器
- Token 自动注入
- 错误统一处理

### 配置说明

```typescript
const apiClient = axios.create({
  baseURL: '/api/v1',  // API 基础路径
  timeout: 30000,       // 请求超时 30 秒
  headers: {
    'Content-Type': 'application/json',
  },
});
```

### 拦截器行为
- **请求拦截器**: 自动从 localStorage 读取 token 并添加到请求头
- **响应拦截器**: 处理 401 未授权错误，自动跳转登录页

---

## 六、API 调用最佳实践

### 1. 在组件中使用

```typescript
import { useState, useEffect } from 'react';
import { projectsApi } from '@/api/projects';
import type { Project } from '@/api/projects';

const ProjectList = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchProjects = async () => {
      setLoading(true);
      try {
        const data = await projectsApi.list();
        setProjects(data);
      } catch (error) {
        message.error('获取项目列表失败');
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  return (
    <Table dataSource={projects} loading={loading} />
  );
};
```

### 2. 错误处理

所有 API 方法在请求失败时会抛出异常，建议使用 try-catch 处理：

```typescript
try {
  const data = await projectsApi.create(newProject);
  message.success('创建成功');
} catch (error) {
  if (axios.isAxiosError(error)) {
    message.error(error.response?.data?.detail || '请求失败');
  }
}
```

### 3. 类型导入

建议从 API 模块导入类型，保持前后端类型一致：

```typescript
import { projectsApi, type Project, type ProjectCreate } from '@/api/projects';
import { sessionsApi, type TestSession } from '@/api/sessions';
import { analysisApi, type FpsAnalysis } from '@/api/analysis';
```

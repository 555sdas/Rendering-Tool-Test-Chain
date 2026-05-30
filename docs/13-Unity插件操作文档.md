# Unity XR数据采集插件操作文档

## 1. 环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Unity | 2022.3 LTS | 2022.3.20f1 |
| XR Plugin Management | 4.4.0 | 最新 |
| OpenXR Plugin | 1.9.1 | 最新 |
| .NET | .NET Standard 2.1 | .NET Standard 2.1 |
| 目标平台 | Android 10+ / Windows 10 | Android 12 / Windows 11 |

## 2. 支持的Unity版本

| Unity版本 | 支持状态 | 说明 |
|-----------|---------|------|
| 2022.3 LTS | ✅ 完全支持 | 推荐版本 |
| 2022.2 | ✅ 支持 | 需测试验证 |
| 2021.3 LTS | ⚠️ 部分支持 | 部分API可能不兼容 |
| 2021.2及以下 | ❌ 不支持 | 缺少必要API |
| 2023.1+ | ⚠️ 需验证 | 新API可能变动 |

## 3. 支持的XR平台

| 平台 | 支持状态 | 测试设备 |
|------|---------|---------|
| Meta Quest 2/3/Pro | ✅ 完全支持 | Quest 2, Quest 3 |
| Pico 4/Neo 3 | ✅ 完全支持 | Pico 4 |
| HTC Vive Focus 3 | ✅ 支持 | Focus 3 |
| HoloLens 2 | ⚠️ 部分支持 | 手势追踪需适配 |
| Magic Leap 2 | ⚠️ 需验证 | 待测试 |
| Android AR (ARCore) | ✅ 支持 | Pixel 6, Samsung S23 |
| iOS AR (ARKit) | ⚠️ 需适配 | 待测试 |
| Unity Editor模拟 | ✅ 支持 | Play Mode测试 |

## 4. 插件导入方式

### 方式一：通过Unity Package Manager导入（推荐）

```
1. 打开Unity项目
2. 菜单栏: Window → Package Manager
3. 点击左上角 "+" 按钮
4. 选择 "Add package from disk..."
5. 选择 unity-xr-collector/package.json 文件
6. 点击 "Open" 导入
```

### 方式二：手动复制到Packages目录

```bash
# 1. 将插件目录复制到项目的Packages文件夹
cp -r unity-xr-collector /path/to/your/unity-project/Packages/com.xrtest.datacollector

# 2. 在manifest.json中添加依赖
# 文件位置: Packages/manifest.json
{
  "dependencies": {
    "com.xrtest.datacollector": "file:com.xrtest.datacollector",
    // ... 其他依赖
  }
}
```

### 方式三：作为Assets导入

```
1. 将Runtime和Editor目录复制到项目的Assets文件夹
   Assets/XRTestCollector/Runtime/
   Assets/XRTestCollector/Editor/

2. Unity会自动编译脚本

3. 如果缺少依赖，需手动安装:
   - Window → Package Manager → XR Plugin Management
   - Window → Package Manager → OpenXR Plugin
```

## 5. 依赖配置

### 5.1 必需依赖包

```json
// Packages/manifest.json 中确保包含:
{
  "dependencies": {
    "com.unity.xr.management": "4.4.0",
    "com.unity.xr.openxr": "1.9.1",
    "com.unity.modules.xr": "1.0.0"
  }
}
```

### 5.2 XR插件配置

```
1. 菜单栏: Edit → Project Settings
2. 选择 XR Plug-in Management
3. 在PC/Mac/Standalone标签页勾选 "OpenXR"
4. 在Android标签页勾选 "OpenXR"
5. 点击 "OpenXR" 子菜单
6. 添加交互配置文件:
   - Oculus Touch Controller Profile
   - HTC Vive Controller Profile
   - 或其他需要的配置文件
```

### 5.3 渲染管线配置（可选）

```
如果使用URP:
1. Window → Package Manager → Universal RP
2. 创建URP Asset: Assets → Create → Rendering → URP Asset
3. Edit → Project Settings → Graphics
4. 将URP Asset赋值给Scriptable Render Pipeline Settings
```

## 6. 快速开始

### 6.1 场景中添加数据采集器

```csharp
// 方式1: 通过菜单快速创建
// 菜单栏: XR Test → Setup → Create XRTestManager

// 方式2: 手动添加
// 1. 在Hierarchy中右键 → Create Empty
// 2. 命名为 "XRTestManager"
// 3. 添加组件: Add Component → XRTestManager
```

### 6.2 配置数据采集

```csharp
using XRTestCollector.Core;

public class MyTestSetup : MonoBehaviour
{
    void Start()
    {
        // 获取或创建管理器
        var manager = XRTestManager.Instance;
        
        // 配置测试
        var config = new XRTestConfig
        {
            sessionName = "MyTestSession",
            sampleIntervalMs = 100,      // 每100ms采样一次
            captureScreenshots = true,    // 捕获截图
            screenshotIntervalSec = 5,    // 每5秒截图
            uploadToServer = true,        // 上传到服务器
            serverUrl = "http://your-server/api/v1/sessions",
            authToken = "your-jwt-token"
        };
        
        manager.Initialize(config);
        
        // 自动开始（如果配置了autoStart）
        // 或手动开始
        manager.StartSession();
    }
}
```

### 6.3 运行时控制

```csharp
// 在任意脚本中控制测试
var manager = XRTestManager.Instance;

// 开始测试
manager.StartSession();

// 暂停测试
manager.PauseSession();

// 恢复测试
manager.ResumeSession();

// 停止测试
manager.StopSession();

// 导出数据
manager.ExportToJson("path/to/save");
manager.ExportToCsv("path/to/save");
```

## 7. Editor窗口使用

### 7.1 打开测试窗口

```
菜单栏: XR Test → Open Test Window
或快捷键: Ctrl+Shift+T (Windows) / Cmd+Shift+T (Mac)
```

### 7.2 窗口功能

| 区域 | 功能 |
|------|------|
| 会话控制 | 开始/暂停/停止/重置会话 |
| 实时数据 | 显示当前FPS、帧时间、内存使用 |
| 配置面板 | 修改采样间隔、截图设置等 |
| 设备信息 | 显示当前设备型号、GPU、系统版本 |
| 导出按钮 | 导出JSON/CSV格式数据 |
| 上传按钮 | 上传数据到服务器 |

## 8. 脚本API参考

### 8.1 XRTestManager

```csharp
// 单例获取
XRTestManager Instance { get; }

// 初始化
void Initialize(XRTestConfig config);

// 会话控制
void StartSession();
void PauseSession();
void ResumeSession();
void StopSession();

// 数据导出
void ExportToJson(string directory);
void ExportToCsv(string directory);

// 数据上传
void UploadToServer(string url, string authToken);

// 事件
Action OnSessionStarted;
Action OnSessionStopped;
Action<PerformanceSample> OnSampleCollected;
Action<string> OnError;
```

### 8.2 XRTestConfig

```csharp
public class XRTestConfig
{
    public string sessionName = "TestSession";      // 会话名称
    public string projectId = "";                   // 项目ID
    public string sceneName = "";                   // 场景名称
    
    // 采样配置
    public float sampleIntervalMs = 100f;           // 采样间隔(ms)
    public bool autoStart = false;                  // 自动开始
    
    // 截图配置
    public bool captureScreenshots = false;         // 是否截图
    public float screenshotIntervalSec = 5f;        // 截图间隔(s)
    public int screenshotWidth = 1920;              // 截图宽度
    public int screenshotHeight = 1080;             // 截图高度
    
    // 上传配置
    public bool uploadToServer = false;             // 是否上传
    public string serverUrl = "";                   // 服务器地址
    public string authToken = "";                   // 认证Token
    public bool uploadInRealTime = false;           // 实时上传
}
```

### 8.3 PerformanceSample

```csharp
public class PerformanceSample
{
    public long timestamp;              // 时间戳(ms)
    public int frameNumber;             // 帧号
    
    // 帧率
    public float fps;                   // 当前FPS
    public float frameTimeMs;           // 帧时间(ms)
    
    // CPU
    public float cpuUsagePercent;       // CPU使用率
    public float cpuTimeMs;             // CPU时间(ms)
    
    // GPU
    public float gpuUsagePercent;       // GPU使用率
    public float gpuTimeMs;             // GPU时间(ms)
    
    // 内存
    public float totalMemoryMB;         // 总内存(MB)
    public float allocatedMemoryMB;     // 已分配内存(MB)
    public float monoHeapSizeMB;        // Mono堆大小(MB)
    public float monoUsedSizeMB;        // Mono已用内存(MB)
    
    // 渲染统计
    public int drawCalls;               // Draw Call数量
    public int setPassCalls;            // SetPass Call数量
    public int triangleCount;           // 三角形数量
    public int vertexCount;             // 顶点数量
    
    // XR特定
    public float xrRenderTimeMs;        // XR渲染时间
    public float xrPoseLatencyMs;       // XR姿态延迟
    public string trackingState;        // 追踪状态
}
```

## 9. 数据导出格式

### 9.1 JSON格式

```json
{
  "sessionInfo": {
    "sessionId": "uuid",
    "sessionName": "MyTest",
    "startTime": "2024-01-01T00:00:00Z",
    "endTime": "2024-01-01T01:00:00Z",
    "durationSec": 3600,
    "deviceInfo": {
      "deviceModel": "Quest 2",
      "osVersion": "Android 12",
      "gpu": "Adreno 650"
    }
  },
  "samples": [
    {
      "timestamp": 1704067200000,
      "frameNumber": 1,
      "fps": 72.5,
      "frameTimeMs": 13.8,
      "cpuUsagePercent": 45.2,
      "gpuUsagePercent": 78.1,
      "totalMemoryMB": 2048.5
    }
  ],
  "statistics": {
    "avgFps": 71.2,
    "minFps": 68.5,
    "maxFps": 72.8,
    "avgFrameTimeMs": 14.1,
    "droppedFrames": 12
  }
}
```

### 9.2 CSV格式

```csv
Timestamp,FrameNumber,FPS,FrameTimeMs,CPU%,GPU%,MemoryMB
1704067200000,1,72.5,13.8,45.2,78.1,2048.5
1704067200100,2,72.3,13.9,44.8,77.5,2050.2
```

## 10. 打包与发布

### 10.1 打包Unity插件

```bash
# 方式1: 导出Unity Package
# 菜单栏: Assets → Export Package...
# 选择 XRTestCollector 目录
# 保存为 XRTestCollector.unitypackage

# 方式2: 作为npm包发布
# 1. 更新 package.json 版本号
# 2. npm publish (如果是私有包，使用私有registry)

# 方式3: Git仓库引用
# 在manifest.json中添加:
"com.xrtest.datacollector": "https://github.com/your-repo/unity-xr-collector.git"
```

### 10.2 构建测试应用

```
1. File → Build Settings
2. 选择目标平台 (Android/Windows)
3. 点击 "Switch Platform"
4. Player Settings:
   - Company Name: YourCompany
   - Product Name: XRTestApp
   - Minimum API Level: 29 (Android 10)
   - Target API Level: 33 (Android 13)
5. 点击 "Build"
```

### 10.3 Android特定配置

```
1. Edit → Project Settings → Player
2. Android标签页:
   - Other Settings:
     - Minimum API Level: 29
     - Target API Level: 33
     - Scripting Backend: IL2CPP
     - Target Architectures: ARM64
   - Publishing Settings:
     - 配置Keystore (发布时)
   - XR Settings:
     - Virtual Reality Supported: ✓
     - Add OpenXR
```

## 11. 常见问题

### Q1: 插件导入后编译错误
```
解决:
1. 检查Unity版本是否 >= 2022.3
2. 检查是否安装了XR Plugin Management
3. 检查.NET版本是否为Standard 2.1
4. 尝试删除Library文件夹重新编译
```

### Q2: 运行时无法获取GPU数据
```
解决:
1. GPU数据在某些平台(如Android)可能无法直接获取
2. 使用Unity Profiler的间接数据
3. 在Editor中测试时可获取完整GPU数据
```

### Q3: 截图功能不工作
```
解决:
1. 检查是否有Camera组件
2. 检查RenderTexture设置
3. 在Android上需要WRITE_EXTERNAL_STORAGE权限
4. 使用Application.persistentDataPath作为保存路径
```

### Q4: 数据上传失败
```
解决:
1. 检查网络连接
2. 检查服务器URL是否正确
3. 检查authToken是否过期
4. 查看Unity Console中的详细错误信息
```

### Q5: 帧率数据不准确
```
解决:
1. 确保在Update()中调用采集
2. 检查Time.unscaledDeltaTime的使用
3. 避免在采集时进行大量计算
4. 使用Unity Profiler验证数据
```

## 12. 最佳实践

### 12.1 性能优化建议

```csharp
// 1. 控制采样频率
var config = new XRTestConfig
{
    sampleIntervalMs = 200  // 不要设置过小，避免影响性能
};

// 2. 避免实时上传
config.uploadInRealTime = false;  // 测试结束后统一上传

// 3. 限制截图数量
config.captureScreenshots = true;
config.screenshotIntervalSec = 10;  // 不要过于频繁
```

### 12.2 测试流程建议

```
1. 准备阶段
   - 配置测试参数
   - 清空上次测试数据
   - 确保设备电量充足

2. 执行阶段
   - 启动应用
   - 开始数据采集
   - 执行测试用例
   - 标记关键时间点

3. 结束阶段
   - 停止数据采集
   - 导出数据
   - 上传到服务器
   - 生成报告
```

## 13. 调试与日志

### 13.1 启用详细日志

```csharp
// 在XRTestManager中设置日志级别
XRTestManager.Instance.logLevel = LogLevel.Verbose;

// 日志级别
public enum LogLevel
{
    None,       // 不输出
    Error,      // 仅错误
    Warning,    // 警告和错误
    Info,       // 一般信息
    Verbose     // 详细信息
}
```

### 13.2 查看日志

```
Unity Console: 查看运行时日志
Log文件: Application.persistentDataPath + "/XRTestLogs/"
Android: /sdcard/Android/data/[package]/files/XRTestLogs/
```

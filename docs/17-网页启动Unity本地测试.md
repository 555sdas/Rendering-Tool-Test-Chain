# 网页启动 Unity 本地测试说明

本版本把测试链路调整为“前端选择、后端启动、Unity 插件采集上传”：

```text
前端项目详情页
  -> 选择项目 / Unity 引擎 / 场景资源 / 渲染质量测试项
  -> 调用后端创建测试任务和测试会话

后端 unity-runner
  -> 读取 backend/resources 下的 Unity 引擎和场景配置
  -> 写入 runtime/unity_tasks 下的任务 JSON
  -> 通过 Unity.exe -executeMethod 启动 Unity

Unity 插件 com.xr.testdatacollector
  -> XRBatchTestRunner 读取任务 JSON
  -> 打开指定场景，配置 XRTestManager
  -> 前 30 秒采集帧率，后 30 秒采集 CPU/GPU/内存/渲染质量等指标
  -> 上传到后端已创建的测试会话
```

## 资源配置位置

Unity 引擎配置：

```text
backend/resources/unity_engines/unity_2022_3_62f3.json
```

当前默认内容指向：

```text
E:/unity_install/2022.3.62f3/Editor/Unity.exe
```

Unity 场景资源配置：

```text
backend/resources/unity_projects/boat_attack_demo_island.json
```

当前默认内容指向：

```text
D:/intellij项目/BoatAttack
Assets/scenes/demo_Island.unity
```

换电脑时主要修改这两个 JSON 里的路径。

## 插件如何接入 Unity 项目

Unity 项目通过 `Packages/manifest.json` 引入本仓库的本地插件包：

```json
{
  "dependencies": {
    "com.xr.testdatacollector": "file:C:/Users/fz121/PycharmProjects/Rendering-Tool-Test-Chain/unity-xr-collector"
  }
}
```

前端启动测试时，如果勾选“缺少插件时自动写入 manifest”，后端会检查目标 Unity 项目的 `Packages/manifest.json`。如果没有 `com.xr.testdatacollector`，会自动写入上述本地 package 依赖。

## 前端如何使用

1. 启动后端和前端。
2. 登录平台。
3. 进入“项目管理”。
4. 点击某个项目的“查看”。
5. 在“Unity 本地测试”区域选择：
   - Unity 引擎
   - 场景资源
   - 采集间隔
   - 帧率采集时长
   - 指标采集时长
   - 渲染质量测试项：光照与阴影、材质与纹理、后处理、物理仿真
6. 点击“启动 Unity 测试”。

后端会立即创建一个新的测试会话，名称仍按 `#数字` 自动递增。Unity 跑完并上传后，该会话会变为已完成，项目详情页刷新后即可进入“分析”查看。

## 后端新增接口

```text
GET  /api/v1/unity-runner/engines
GET  /api/v1/unity-runner/scenes?project_id=1
POST /api/v1/unity-runner/test-tasks/start
```

`POST /test-tasks/start` 会创建：

- `TestTask`：记录网页启动的 Unity 本地测试任务。
- `TestSession`：记录本次测试会话，并绑定到当前项目。
- `runtime/unity_tasks/*.json`：传给 Unity 插件的任务参数。
- `runtime/unity_logs/*.log`：Unity 本次启动的日志。

## Unity 命令入口

后端启动 Unity 时调用：

```text
XRDataCollector.Editor.XRBatchTestRunner.RunFromCommandLine
```

对应命令形态：

```powershell
Unity.exe `
  -projectPath "D:/intellij项目/BoatAttack" `
  -executeMethod XRDataCollector.Editor.XRBatchTestRunner.RunFromCommandLine `
  -xrTaskConfig "backend/runtime/unity_tasks/unity_task_x_session_y.json" `
  -logFile "backend/runtime/unity_logs/unity_task_x_session_y.log"
```

任务 JSON 中包含后端已创建的 `platformSessionId` 和 `uploadUrl`，所以 Unity 插件不会再新建会话，而是直接把采集结果上传到指定会话。

## 注意事项

- 普通网页不能直接访问本机磁盘或启动 Unity，因此必须通过后端本地 Runner 启动。
- 不建议把 Unity Editor 本体放进项目仓库，只在后端资源配置里登记路径。
- 场景资源应登记为“Unity 项目目录 + 场景相对路径”，不要只拷贝单个 `.unity` 文件。
- 如果目标 Unity 项目已经在 Unity 中打开，再从网页启动同一个项目可能会遇到项目锁。正式演示时建议先关闭当前打开的同项目 Unity 窗口。

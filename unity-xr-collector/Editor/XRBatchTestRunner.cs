using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using XRDataCollector.Core;

namespace XRDataCollector.Editor
{
    public static class XRBatchTestRunner
    {
        private const string TaskConfigArg = "-xrTaskConfig";
        private const string QuitOnCompleteKey = "XRDataCollector.BatchQuitOnComplete";
        private const string PendingExitCodeKey = "XRDataCollector.BatchPendingExitCode";
        private const string PendingTaskRelativePath = "Library/XRDataCollector/pending-task.json";
        private const string PendingTaskConfigKey = "XRDataCollector.PendingTaskConfigJson";
        private const string PendingExitReadyAtKey = "XRDataCollector.BatchPendingExitReadyAt";
        private const string PendingCollectionReadyAtKey = "XRDataCollector.BatchPendingCollectionReadyAt";
        private const double ExitDelayAfterUploadSeconds = 3.5d;
        private const double ExitDelayAfterPlayModeExitSeconds = 2.5d;
        private static XRBatchTaskConfig taskConfig;
        private static bool shutdownScheduled;

        [InitializeOnLoadMethod]
        private static void ResumePendingExit()
        {
            EditorApplication.update -= ExitWhenEditorReady;
            EditorApplication.update -= PollPendingTask;
            EditorApplication.update -= StartPendingCollectionWhenReady;
            EditorApplication.playModeStateChanged -= OnGlobalPlayModeStateChanged;
            EditorApplication.update -= PollStopRequestOnUpdate;
            EditorApplication.update += PollPendingTask;
            EditorApplication.playModeStateChanged += OnGlobalPlayModeStateChanged;
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            if (XROrchestrationRunner.IsOrchestrationActive())
                return;
            if (!string.IsNullOrEmpty(SessionState.GetString(PendingTaskConfigKey, string.Empty)))
            {
                EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
                if (EditorApplication.isPlaying)
                {
                    var activeManager = XRTestManager.Instance != null
                        ? XRTestManager.Instance
                        : UnityEngine.Object.FindObjectOfType<XRTestManager>();
                    if (activeManager != null && activeManager.IsCollecting)
                        EditorApplication.update += ReapplyConfigWhileCollectingOnce;
                    else
                    {
                        SessionState.SetString(
                            PendingCollectionReadyAtKey,
                            (EditorApplication.timeSinceStartup + 2.0d).ToString("R"));
                        EditorApplication.update += StartPendingCollectionWhenReady;
                    }
                }
            }
            if (SessionState.GetInt(PendingExitCodeKey, -1) >= 0)
                EditorApplication.update += ExitWhenEditorReady;
            if (!string.IsNullOrEmpty(SessionState.GetString(PendingTaskConfigKey, string.Empty)))
                EditorApplication.update += PollStopRequestOnUpdate;
        }

        private static void PollStopRequestOnUpdate()
        {
            if (string.IsNullOrEmpty(SessionState.GetString(PendingTaskConfigKey, string.Empty)))
            {
                EditorApplication.update -= PollStopRequestOnUpdate;
                return;
            }

            PollStopRequest();
        }

        private static void OnGlobalPlayModeStateChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.ExitingPlayMode)
                return;

            taskConfig = null;
            EditorApplication.update -= StartPendingCollectionWhenReady;
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            SessionState.EraseString(PendingCollectionReadyAtKey);
            if (SessionState.GetInt(PendingExitCodeKey, -1) >= 0)
            {
                SessionState.SetString(
                    PendingExitReadyAtKey,
                    (EditorApplication.timeSinceStartup + ExitDelayAfterPlayModeExitSeconds).ToString("R"));
                ScheduleEditorExitPolling();
            }
            else if (!SessionState.GetBool(QuitOnCompleteKey, false))
            {
                SessionState.EraseString(PendingTaskConfigKey);
            }
        }

        public static void RunFromCommandLine()
        {
            string configPath = GetArgumentValue(TaskConfigArg);
            RunFromConfigPath(configPath);
        }

        public static void RunFromConfigPath(string configPath)
        {
            if (string.IsNullOrEmpty(configPath))
                throw new InvalidOperationException("缺少 -xrTaskConfig 参数。");
            if (!File.Exists(configPath))
                throw new FileNotFoundException("任务配置文件不存在。", configPath);

            string json = File.ReadAllText(configPath);
            if (XROrchestrationConfigParser.IsMultiSceneConfig(json))
            {
                XROrchestrationRunner.RunFromConfigPath(configPath, json);
                return;
            }

            taskConfig = JsonUtility.FromJson<XRBatchTaskConfig>(json);
            if (taskConfig == null)
                throw new InvalidOperationException("任务配置解析失败。");

            SessionState.SetString(PendingTaskConfigKey, json);
            EnableFrameTimingStatsInternal();

            Debug.Log($"[XRBatchTestRunner] 已读取任务配置：{configPath}");
            Debug.Log($"[XRBatchTestRunner] 任务 {taskConfig.taskId} / 平台会话 {taskConfig.platformSessionId}，项目 {taskConfig.projectId}，场景 {taskConfig.unityScenePath}");

            SessionState.SetBool(QuitOnCompleteKey, taskConfig.quitOnComplete);
            SessionState.SetInt(PendingExitCodeKey, -1);
            SessionState.EraseString(PendingExitReadyAtKey);
            SessionState.EraseString(PendingCollectionReadyAtKey);
            shutdownScheduled = false;
            OpenConfiguredSceneInternal(taskConfig.unityProjectPath, taskConfig.unityScenePath);
            var manager = EnsureManagerInternal();
            ApplyTaskConfig(manager, taskConfig);

            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
            EditorApplication.update -= PollStopRequestOnUpdate;
            EditorApplication.update += PollStopRequestOnUpdate;
            EditorApplication.isPlaying = true;
        }

        private static void PollPendingTask()
        {
            if (EditorApplication.isCompiling || EditorApplication.isPlayingOrWillChangePlaymode)
            {
                PollStopRequest();
                return;
            }

            string inboxPath = Path.GetFullPath(PendingTaskRelativePath);
            if (!File.Exists(inboxPath)) return;
            try
            {
                var request = JsonUtility.FromJson<PendingTaskRequest>(File.ReadAllText(inboxPath));
                File.Delete(inboxPath);
                if (request == null || string.IsNullOrEmpty(request.configPath))
                    throw new InvalidOperationException("待执行任务没有 configPath。");
                RunFromConfigPath(request.configPath);
            }
            catch (Exception exception)
            {
                Debug.LogError("[XRBatchTestRunner] 读取待执行任务失败：" + exception);
            }
        }

        private static void PollStopRequest()
        {
            int taskId = ResolveStopTaskId();
            if (taskId <= 0) return;

            string path = Path.GetFullPath($"Library/XRDataCollector/stop-task-{taskId}");
            if (!File.Exists(path)) return;
            File.Delete(path);

            EnsureTaskConfigLoaded();
            Debug.Log($"[XRBatchTestRunner] 收到网页停止请求，任务 {taskId}。");

            EditorApplication.update -= StartPendingCollectionWhenReady;
            SessionState.EraseString(PendingCollectionReadyAtKey);

            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
            if (manager != null)
            {
                manager.OnDataUploaded -= OnDataUploaded;
                manager.OnSessionStopped -= OnSessionStopped;
                if (manager.IsCollecting)
                    manager.StopCollection();
                else
                    manager.PrepareForShutdown();
            }

            Finish(0);
        }

        private static void EnsureTaskConfigLoaded()
        {
            if (taskConfig != null) return;

            string json = SessionState.GetString(PendingTaskConfigKey, string.Empty);
            if (string.IsNullOrEmpty(json)) return;

            taskConfig = JsonUtility.FromJson<XRBatchTaskConfig>(json);
        }

        private static int ResolveStopTaskId()
        {
            EnsureTaskConfigLoaded();
            if (taskConfig != null && taskConfig.taskId > 0)
                return taskConfig.taskId;

            string configJson = SessionState.GetString(PendingTaskConfigKey, string.Empty);
            if (!string.IsNullOrEmpty(configJson))
            {
                var cached = JsonUtility.FromJson<XRBatchTaskConfig>(configJson);
                if (cached != null && cached.taskId > 0)
                    return cached.taskId;
            }

            string stopDir = Path.GetFullPath("Library/XRDataCollector");
            if (!Directory.Exists(stopDir)) return 0;

            foreach (string file in Directory.GetFiles(stopDir, "stop-task-*"))
            {
                string name = Path.GetFileName(file);
                const string prefix = "stop-task-";
                if (!name.StartsWith(prefix, StringComparison.Ordinal)) continue;
                if (int.TryParse(name.Substring(prefix.Length), out int taskId))
                    return taskId;
            }

            return 0;
        }

        private static void OnPlayModeStateChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredPlayMode) return;

            SchedulePendingCollection();
            RequestFlythroughIfConfigured();
        }

        private static void ReapplyConfigWhileCollectingOnce()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorApplication.update -= ReapplyConfigWhileCollectingOnce;
                return;
            }

            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
            if (manager == null || !manager.IsCollecting)
            {
                EditorApplication.update -= ReapplyConfigWhileCollectingOnce;
                return;
            }

            EditorApplication.update -= ReapplyConfigWhileCollectingOnce;
            EnsureTaskConfigApplied(manager);
            manager.EnsureCollectorsActiveAfterReload();
            RequestFlythroughIfConfigured();
            Debug.Log("[XRBatchTestRunner] 脚本重载后已恢复进行中的采集任务。");
        }

        private static void RequestFlythroughIfConfigured()
        {
            if (taskConfig != null)
            {
                if (!taskConfig.forceAutoFlythroughOnStart)
                    return;
            }
            else
            {
                string cachedJson = SessionState.GetString(PendingTaskConfigKey, string.Empty);
                if (string.IsNullOrEmpty(cachedJson))
                    return;
                var cached = JsonUtility.FromJson<XRBatchTaskConfig>(cachedJson);
                if (cached == null || !cached.forceAutoFlythroughOnStart)
                    return;
            }

            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
            TestSceneFlythroughActivator.RequestActivation(manager);
        }

        private static void SchedulePendingCollection()
        {
            SessionState.SetString(
                PendingCollectionReadyAtKey,
                (EditorApplication.timeSinceStartup + 2.0d).ToString("R"));
            EditorApplication.update -= StartPendingCollectionWhenReady;
            EditorApplication.update += StartPendingCollectionWhenReady;
            Debug.Log("[XRBatchTestRunner] Play Mode 已进入，等待 Editor 稳定后启动采集。");
        }

        private static void StartPendingCollectionWhenReady()
        {
            if (!EditorApplication.isPlaying || EditorApplication.isCompiling || EditorApplication.isUpdating)
                return;

            if (double.TryParse(SessionState.GetString(PendingCollectionReadyAtKey, "0"), out double readyAt) &&
                EditorApplication.timeSinceStartup < readyAt)
                return;

            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();

            if (manager == null)
            {
                FinishWithError("进入运行模式后未找到 XRTestManager。");
                return;
            }

            EditorApplication.update -= StartPendingCollectionWhenReady;
            SessionState.EraseString(PendingCollectionReadyAtKey);

            if (manager.IsCollecting)
            {
                EnsureTaskConfigApplied(manager);
                manager.EnsureCollectorsActiveAfterReload();
                Debug.Log("[XRBatchTestRunner] 采集已在运行，已重新应用配置并恢复采集器。");
                return;
            }

            EnsureTaskConfigApplied(manager);

            manager.OnDataUploaded -= OnDataUploaded;
            manager.OnDataUploaded += OnDataUploaded;
            manager.OnSessionStopped -= OnSessionStopped;
            manager.OnSessionStopped += OnSessionStopped;

            manager.StartCollection();
            Debug.Log("[XRBatchTestRunner] Editor 已稳定，冷启动采集已开始。");
        }

        private static void OnSessionStopped()
        {
            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
            if (manager == null || manager.Config == null || !manager.Config.enableNetworkUpload)
                Finish(0);
        }

        private static void OnDataUploaded(bool success)
        {
            Finish(success ? 0 : 1);
        }

        private static void Finish(int exitCode)
        {
            if (shutdownScheduled)
                return;
            shutdownScheduled = true;

            DetachManagerCallbacks();

            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            EditorApplication.update -= StartPendingCollectionWhenReady;
            EditorApplication.update -= PollStopRequestOnUpdate;
            SessionState.EraseString(PendingCollectionReadyAtKey);
            taskConfig = null;

            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
            manager?.PrepareForShutdown();

            bool quitEditor = SessionState.GetBool(QuitOnCompleteKey, false);
            SchedulePlayModeExit();

            if (!quitEditor)
            {
                SessionState.EraseString(PendingTaskConfigKey);
                SessionState.EraseBool(QuitOnCompleteKey);
                Debug.Log("[XRBatchTestRunner] 测试结束，已安排退出 Play Mode，保持 Unity Editor 打开。");
                return;
            }

            SessionState.SetInt(PendingExitCodeKey, exitCode);
            SessionState.SetString(
                PendingExitReadyAtKey,
                (EditorApplication.timeSinceStartup + ExitDelayAfterUploadSeconds).ToString("R"));
            ScheduleEditorExitPolling();
            Debug.Log($"[XRBatchTestRunner] 已安排 Editor 退出（exitCode={exitCode}），先等待运行时资源释放。");
        }

        private static void SchedulePlayModeExit()
        {
            EditorApplication.delayCall += () =>
            {
                if (EditorApplication.isPlaying)
                    EditorApplication.isPlaying = false;
            };
        }

        private static void DetachManagerCallbacks()
        {
            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
            if (manager == null)
                return;

            manager.OnDataUploaded -= OnDataUploaded;
            manager.OnSessionStopped -= OnSessionStopped;
        }

        internal static void ScheduleEditorExitPollingInternal()
        {
            EditorApplication.update -= ExitWhenEditorReady;
            EditorApplication.update += ExitWhenEditorReady;
        }

        private static void ScheduleEditorExitPolling()
        {
            ScheduleEditorExitPollingInternal();
        }

        private static void ExitWhenEditorReady()
        {
            int exitCode = SessionState.GetInt(PendingExitCodeKey, -1);
            if (exitCode < 0 || EditorApplication.isPlayingOrWillChangePlaymode ||
                EditorApplication.isCompiling || EditorApplication.isUpdating)
                return;

            if (double.TryParse(SessionState.GetString(PendingExitReadyAtKey, "0"), out double readyAt) &&
                EditorApplication.timeSinceStartup < readyAt)
                return;

            EditorApplication.update -= ExitWhenEditorReady;
            SessionState.EraseInt(PendingExitCodeKey);
            SessionState.EraseBool(QuitOnCompleteKey);
            SessionState.EraseString(PendingTaskConfigKey);
            SessionState.EraseString(PendingExitReadyAtKey);
            shutdownScheduled = false;
            Debug.Log($"[XRBatchTestRunner] Editor 即将退出，exitCode={exitCode}。");
            EditorApplication.Exit(exitCode);
        }

        private static void FinishWithError(string message)
        {
            Debug.LogError("[XRBatchTestRunner] " + message);
            Finish(1);
        }

        internal static void OpenConfiguredSceneInternal(string unityProjectPath, string unityScenePath)
        {
            if (string.IsNullOrEmpty(unityScenePath)) return;
            string assetPath = unityScenePath.Replace("\\", "/");
            string projectPath = string.IsNullOrEmpty(unityProjectPath)
                ? Directory.GetCurrentDirectory()
                : unityProjectPath;
            if (Path.IsPathRooted(assetPath))
            {
                string assetsRoot = Path.Combine(projectPath, "Assets").Replace("\\", "/").TrimEnd('/');
                if (!assetPath.StartsWith(assetsRoot + "/", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("场景不在当前 Unity 项目的 Assets 目录中：" + assetPath);
                assetPath = "Assets/" + assetPath.Substring(assetsRoot.Length + 1);
            }
            string absolutePath = Path.Combine(projectPath, assetPath).Replace("\\", "/");
            if (!File.Exists(absolutePath))
                throw new FileNotFoundException("Unity 场景文件不存在。", absolutePath);

            var openedScene = EditorSceneManager.OpenScene(assetPath, OpenSceneMode.Single);
            if (!openedScene.IsValid() || openedScene.path != assetPath)
                throw new InvalidOperationException($"场景打开结果不正确，期望 {assetPath}，实际 {openedScene.path}");
            Debug.Log($"[XRBatchTestRunner] 场景已打开并设为活动场景：{openedScene.path}");
            if (UnityEngine.Object.FindObjectOfType<Camera>() == null)
                Debug.LogWarning($"[XRBatchTestRunner] 场景 {openedScene.path} 中没有启用的 Camera，Game 窗口将显示 No cameras rendering。");
        }

        internal static XRTestManager EnsureManagerInternal()
        {
            var manager = UnityEngine.Object.FindObjectOfType<XRTestManager>();
            if (manager != null) return manager;

            var go = new GameObject("XRTestManager");
            manager = go.AddComponent<XRTestManager>();
            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            return manager;
        }

        internal static void EnableFrameTimingStatsInternal()
        {
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
            }
            catch (Exception exception)
            {
                Debug.LogWarning("[XRBatchTestRunner] 无法启用 Frame Timing Stats：" + exception.Message);
            }
        }

        private static void EnsureTaskConfigApplied(XRTestManager manager)
        {
            if (taskConfig == null)
            {
                string cachedJson = SessionState.GetString(PendingTaskConfigKey, string.Empty);
                if (!string.IsNullOrEmpty(cachedJson))
                    taskConfig = JsonUtility.FromJson<XRBatchTaskConfig>(cachedJson);
            }

            if (taskConfig == null)
            {
                Debug.LogWarning("[XRBatchTestRunner] 进入 Play Mode 时未找到任务配置，将使用场景内已有配置。");
                return;
            }

            ApplyTaskConfig(manager, taskConfig);
            manager.Initialize(manager.Config);
            Debug.Log("[XRBatchTestRunner] 已在 Play Mode 重新应用网页任务配置。");
        }

        internal static void ApplySceneRunConfig(
            XRTestManager manager,
            XRSceneRunConfig scene,
            XROrchestrationTaskConfig root)
        {
            var config = manager.Config;
            config.sessionName = string.IsNullOrEmpty(scene.sessionName) ? "Unity Web Test" : scene.sessionName;
            config.collectInterval = scene.collectInterval > 0 ? scene.collectInterval : 1f;
            config.frameRateDurationSeconds = scene.frameRateDurationSeconds > 0 ? scene.frameRateDurationSeconds : 30f;
            config.metricsDurationSeconds = scene.metricsDurationSeconds > 0 ? scene.metricsDurationSeconds : 30f;
            config.collectFrameRate = scene.collectFrameRate;
            config.collectFrameTime = scene.collectFrameTime;
            config.collectCpuUsage = scene.collectCpuUsage;
            config.collectGpuUsage = scene.collectGpuUsage;
            config.collectMemory = scene.collectMemory;
            config.collectDeviceInfo = scene.collectDeviceInfo;
            config.collectRenderingStats = scene.collectRenderingStats;
            config.collectRenderQuality = scene.collectRenderQuality;
            config.platformBaseUrl = scene.platformBaseUrl;
            config.uploadUrl = scene.uploadUrl;
            config.progressUrl = !string.IsNullOrEmpty(scene.progressUrl)
                ? scene.progressUrl
                : root != null ? root.progressUrl : string.Empty;
            config.projectId = root != null ? root.projectId : 0;
            config.projectName = scene.projectName;
            config.sceneId = scene.sceneId;
            config.platformSessionId = scene.platformSessionId;
            config.testTaskId = scene.taskId;
            config.progressTaskId = root != null ? root.parentTaskId : scene.taskId;
            config.runMode = root != null ? root.runMode : "single_scene";
            config.batchId = root != null ? root.batchId : 0;
            config.batchItemId = scene.batchItemId;
            config.sceneIndex = scene.sceneIndex;
            config.sceneTotal = scene.sceneTotal;
            config.attempt = scene.attempt > 0 ? scene.attempt : 1;
            config.sceneDisplayName = scene.sceneDisplayName;
            config.deviceToken = root != null ? root.deviceToken : string.Empty;
            config.enableNetworkUpload = scene.enableNetworkUpload;
            config.autoCreateSession = scene.autoCreateSession;
            config.autoStart = scene.autoStart;
            config.quitOnComplete = root != null && root.quitOnComplete;
            config.forceAutoFlythroughOnStart = scene.forceAutoFlythroughOnStart;

            if (scene.qualityChecks != null)
            {
                config.testLightingQuality = scene.qualityChecks.lighting;
                config.testMaterialQuality = scene.qualityChecks.materials;
                config.testPostProcessingQuality = scene.qualityChecks.postProcessing;
                config.testPhysicsQuality = scene.qualityChecks.physics;
            }

            if (scene.qualityMetricChecks != null)
            {
                config.testLightingActiveLights = scene.qualityMetricChecks.lightingActiveLights;
                config.testLightingRealtimeLights = scene.qualityMetricChecks.lightingRealtimeLights;
                config.testLightingShadowCasters = scene.qualityMetricChecks.lightingShadowCasters;
                config.testLightingReflectionProbes = scene.qualityMetricChecks.lightingReflectionProbes;
                config.testLightingExposureArtifacts = scene.qualityMetricChecks.lightingExposureArtifacts;
                config.testMaterialSlots = scene.qualityMetricChecks.materialSlots;
                config.testMaterialUniqueMaterials = scene.qualityMetricChecks.materialUniqueMaterials;
                config.testMaterialTransparentMaterials = scene.qualityMetricChecks.materialTransparentMaterials;
                config.testMaterialDrawCalls = scene.qualityMetricChecks.materialDrawCalls;
                config.testMaterialTextureMemory = scene.qualityMetricChecks.materialTextureMemory;
                config.testPostProcessVolumes = scene.qualityMetricChecks.postProcessVolumes;
                config.testPostProcessRenderTextures = scene.qualityMetricChecks.postProcessRenderTextures;
                config.testPostProcessRenderTextureMemory = scene.qualityMetricChecks.postProcessRenderTextureMemory;
                config.testPostProcessGpuFrameBudget = scene.qualityMetricChecks.postProcessGpuFrameBudget;
                config.testPostProcessWarnings = scene.qualityMetricChecks.postProcessWarnings;
                config.testPhysicsRigidbodies = scene.qualityMetricChecks.physicsRigidbodies;
                config.testPhysicsColliders = scene.qualityMetricChecks.physicsColliders;
                config.testPhysicsPenetration = scene.qualityMetricChecks.physicsPenetration;
                config.testPhysicsPoseLatency = scene.qualityMetricChecks.physicsPoseLatency;
                config.testPhysicsPredictionError = scene.qualityMetricChecks.physicsPredictionError;
                config.testPhysicsLongFrames = scene.qualityMetricChecks.physicsLongFrames;
            }

            EditorUtility.SetDirty(manager);
        }

        private static void ApplyTaskConfig(XRTestManager manager, XRBatchTaskConfig task)
        {
            var config = manager.Config;
            config.sessionName = string.IsNullOrEmpty(task.sessionName) ? "Unity Web Test" : task.sessionName;
            config.collectInterval = task.collectInterval > 0 ? task.collectInterval : 1f;
            config.frameRateDurationSeconds = task.frameRateDurationSeconds > 0 ? task.frameRateDurationSeconds : 30f;
            config.metricsDurationSeconds = task.metricsDurationSeconds > 0 ? task.metricsDurationSeconds : 30f;
            config.collectFrameRate = task.collectFrameRate;
            config.collectFrameTime = task.collectFrameTime;
            config.collectCpuUsage = task.collectCpuUsage;
            config.collectGpuUsage = task.collectGpuUsage;
            config.collectMemory = task.collectMemory;
            config.collectDeviceInfo = task.collectDeviceInfo;
            config.collectRenderingStats = task.collectRenderingStats;
            config.collectRenderQuality = task.collectRenderQuality;
            config.platformBaseUrl = task.platformBaseUrl;
            config.uploadUrl = task.uploadUrl;
            config.progressUrl = task.progressUrl;
            config.projectId = task.projectId;
            config.projectName = task.projectName;
            config.sceneId = task.sceneId;
            config.platformSessionId = task.platformSessionId;
            config.testTaskId = task.taskId;
            config.progressTaskId = task.taskId;
            config.runMode = "single_scene";
            config.batchId = 0;
            config.batchItemId = 0;
            config.sceneIndex = 0;
            config.sceneTotal = 0;
            config.attempt = 1;
            config.sceneDisplayName = string.Empty;
            config.deviceToken = task.deviceToken;
            config.enableNetworkUpload = task.enableNetworkUpload;
            config.autoCreateSession = task.autoCreateSession;
            config.autoStart = task.autoStart;
            config.quitOnComplete = task.quitOnComplete;
            config.forceAutoFlythroughOnStart = task.forceAutoFlythroughOnStart;

            if (task.qualityChecks != null)
            {
                config.testLightingQuality = task.qualityChecks.lighting;
                config.testMaterialQuality = task.qualityChecks.materials;
                config.testPostProcessingQuality = task.qualityChecks.postProcessing;
                config.testPhysicsQuality = task.qualityChecks.physics;
            }

            if (task.qualityMetricChecks != null)
            {
                config.testLightingActiveLights = task.qualityMetricChecks.lightingActiveLights;
                config.testLightingRealtimeLights = task.qualityMetricChecks.lightingRealtimeLights;
                config.testLightingShadowCasters = task.qualityMetricChecks.lightingShadowCasters;
                config.testLightingReflectionProbes = task.qualityMetricChecks.lightingReflectionProbes;
                config.testLightingExposureArtifacts = task.qualityMetricChecks.lightingExposureArtifacts;
                config.testMaterialSlots = task.qualityMetricChecks.materialSlots;
                config.testMaterialUniqueMaterials = task.qualityMetricChecks.materialUniqueMaterials;
                config.testMaterialTransparentMaterials = task.qualityMetricChecks.materialTransparentMaterials;
                config.testMaterialDrawCalls = task.qualityMetricChecks.materialDrawCalls;
                config.testMaterialTextureMemory = task.qualityMetricChecks.materialTextureMemory;
                config.testPostProcessVolumes = task.qualityMetricChecks.postProcessVolumes;
                config.testPostProcessRenderTextures = task.qualityMetricChecks.postProcessRenderTextures;
                config.testPostProcessRenderTextureMemory = task.qualityMetricChecks.postProcessRenderTextureMemory;
                config.testPostProcessGpuFrameBudget = task.qualityMetricChecks.postProcessGpuFrameBudget;
                config.testPostProcessWarnings = task.qualityMetricChecks.postProcessWarnings;
                config.testPhysicsRigidbodies = task.qualityMetricChecks.physicsRigidbodies;
                config.testPhysicsColliders = task.qualityMetricChecks.physicsColliders;
                config.testPhysicsPenetration = task.qualityMetricChecks.physicsPenetration;
                config.testPhysicsPoseLatency = task.qualityMetricChecks.physicsPoseLatency;
                config.testPhysicsPredictionError = task.qualityMetricChecks.physicsPredictionError;
                config.testPhysicsLongFrames = task.qualityMetricChecks.physicsLongFrames;
            }

            EditorUtility.SetDirty(manager);
            var requestedSummary = task.requestedMetricIds != null && task.requestedMetricIds.Length > 0
                ? string.Join("、", task.requestedMetricIds)
                : "（未提供 requestedMetricIds，沿用布尔开关）";
            var supportSummary = task.supportMetricIds != null && task.supportMetricIds.Length > 0
                ? string.Join("、", task.supportMetricIds)
                : "无";
            Debug.Log(
                "[XRBatchTestRunner] 已应用采集配置：" +
                $"间隔={config.collectInterval:F2}s, 帧率阶段={config.frameRateDurationSeconds:F1}s, 指标阶段={config.metricsDurationSeconds:F1}s, " +
                $"性能项 FPS={config.collectFrameRate}, 帧时间={config.collectFrameTime}, CPU={config.collectCpuUsage}, GPU={config.collectGpuUsage}, 内存={config.collectMemory}, 设备={config.collectDeviceInfo}, " +
                $"渲染统计={config.collectRenderingStats}, 渲染质量={config.collectRenderQuality}, " +
                $"质量项 光照={config.testLightingQuality}, 材质={config.testMaterialQuality}, 后处理={config.testPostProcessingQuality}, 物理={config.testPhysicsQuality}"
            );
            Debug.Log($"[XRBatchTestRunner] 用户选择：{requestedSummary}");
            Debug.Log($"[XRBatchTestRunner] 内部支撑采集：{supportSummary}");
        }

        private static string GetArgumentValue(string name)
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == name)
                    return args[i + 1];
            }
            return null;
        }

        [Serializable]
        private class XRBatchTaskConfig
        {
            public int taskId;
            public int platformSessionId;
            public string sessionName;
            public int projectId;
            public int sceneId;
            public string projectName;
            public string platformBaseUrl;
            public string uploadUrl;
            public string progressUrl;
            public string deviceToken;
            public string unityProjectPath;
            public string unityScenePath;
            public float collectInterval;
            public float frameRateDurationSeconds;
            public float metricsDurationSeconds;
            public bool collectFrameRate = true;
            public bool collectFrameTime = true;
            public bool collectCpuUsage = true;
            public bool collectGpuUsage = true;
            public bool collectMemory = true;
            public bool collectDeviceInfo = true;
            public bool collectRenderingStats = true;
            public bool collectRenderQuality = true;
            public int testScopeVersion = 1;
            public string[] requestedMetricIds;
            public string[] supportMetricIds;
            public bool enableNetworkUpload;
            public bool autoCreateSession;
            public bool autoStart;
            public bool quitOnComplete;
            public bool forceAutoFlythroughOnStart = true;
            public XRBatchQualityChecks qualityChecks;
            public XRBatchQualityMetricChecks qualityMetricChecks;
        }

        [Serializable]
        private class PendingTaskRequest
        {
            public string configPath;
        }

        [Serializable]
        private class XRBatchQualityChecks
        {
            public bool lighting = true;
            public bool materials = true;
            public bool postProcessing = true;
            public bool physics = true;
        }

        [Serializable]
        private class XRBatchQualityMetricChecks
        {
            public bool lightingActiveLights = true;
            public bool lightingRealtimeLights = true;
            public bool lightingShadowCasters = true;
            public bool lightingReflectionProbes = true;
            public bool lightingExposureArtifacts = true;
            public bool materialSlots = true;
            public bool materialUniqueMaterials = true;
            public bool materialTransparentMaterials = true;
            public bool materialDrawCalls = true;
            public bool materialTextureMemory = true;
            public bool postProcessVolumes = true;
            public bool postProcessRenderTextures = true;
            public bool postProcessRenderTextureMemory = true;
            public bool postProcessGpuFrameBudget = true;
            public bool postProcessWarnings = true;
            public bool physicsRigidbodies = true;
            public bool physicsColliders = true;
            public bool physicsPenetration = true;
            public bool physicsPoseLatency = true;
            public bool physicsPredictionError = true;
            public bool physicsLongFrames = true;
        }
    }
}

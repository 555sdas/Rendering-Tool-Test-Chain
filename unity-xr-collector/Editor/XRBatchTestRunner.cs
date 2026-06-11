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
        private static XRBatchTaskConfig taskConfig;
        private static bool exitAfterUpload;

        public static void RunFromCommandLine()
        {
            string configPath = GetArgumentValue(TaskConfigArg);
            if (string.IsNullOrEmpty(configPath))
                throw new InvalidOperationException("缺少 -xrTaskConfig 参数。");
            if (!File.Exists(configPath))
                throw new FileNotFoundException("任务配置文件不存在。", configPath);

            string json = File.ReadAllText(configPath);
            taskConfig = JsonUtility.FromJson<XRBatchTaskConfig>(json);
            if (taskConfig == null)
                throw new InvalidOperationException("任务配置解析失败。");

            Debug.Log($"[XRBatchTestRunner] 已读取任务配置：{configPath}");
            Debug.Log($"[XRBatchTestRunner] 任务 {taskConfig.taskId} / 平台会话 {taskConfig.platformSessionId}，项目 {taskConfig.projectId}，场景 {taskConfig.unityScenePath}");

            exitAfterUpload = taskConfig.quitOnComplete;
            OpenConfiguredScene(taskConfig);
            var manager = EnsureManager();
            ApplyTaskConfig(manager, taskConfig);

            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
            EditorApplication.isPlaying = true;
        }

        private static void OnPlayModeStateChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredPlayMode) return;

            var manager = XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();

            if (manager == null)
            {
                FinishWithError("进入运行模式后未找到 XRTestManager。");
                return;
            }

            manager.OnDataUploaded -= OnDataUploaded;
            manager.OnDataUploaded += OnDataUploaded;
            manager.OnSessionStopped -= OnSessionStopped;
            manager.OnSessionStopped += OnSessionStopped;

            if (!manager.IsCollecting)
                manager.StartCollection();
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
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;

            if (!exitAfterUpload)
                return;

            if (EditorApplication.isPlaying)
                EditorApplication.isPlaying = false;

            EditorApplication.delayCall += () => EditorApplication.Exit(exitCode);
        }

        private static void FinishWithError(string message)
        {
            Debug.LogError("[XRBatchTestRunner] " + message);
            Finish(1);
        }

        private static void OpenConfiguredScene(XRBatchTaskConfig config)
        {
            if (string.IsNullOrEmpty(config.unityScenePath)) return;
            string scenePath = config.unityScenePath.Replace("\\", "/");
            if (!File.Exists(scenePath))
            {
                string projectPath = string.IsNullOrEmpty(config.unityProjectPath)
                    ? Directory.GetCurrentDirectory()
                    : config.unityProjectPath;
                scenePath = Path.Combine(projectPath, scenePath).Replace("\\", "/");
            }
            if (!File.Exists(scenePath))
                throw new FileNotFoundException("Unity 场景文件不存在。", scenePath);

            EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
            Debug.Log($"[XRBatchTestRunner] 场景已打开：{scenePath}");
        }

        private static XRTestManager EnsureManager()
        {
            var manager = UnityEngine.Object.FindObjectOfType<XRTestManager>();
            if (manager != null) return manager;

            var go = new GameObject("XRTestManager");
            manager = go.AddComponent<XRTestManager>();
            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            return manager;
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
            config.platformBaseUrl = task.platformBaseUrl;
            config.uploadUrl = task.uploadUrl;
            config.projectId = task.projectId;
            config.projectName = task.projectName;
            config.sceneId = task.sceneId;
            config.platformSessionId = task.platformSessionId;
            config.testTaskId = task.taskId;
            config.deviceToken = task.deviceToken;
            config.enableNetworkUpload = task.enableNetworkUpload;
            config.autoCreateSession = task.autoCreateSession;
            config.autoStart = task.autoStart;
            config.quitOnComplete = task.quitOnComplete;

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
            Debug.Log(
                "[XRBatchTestRunner] 已应用采集配置：" +
                $"间隔={config.collectInterval:F2}s, 帧率阶段={config.frameRateDurationSeconds:F1}s, 指标阶段={config.metricsDurationSeconds:F1}s, " +
                $"性能项 FPS={config.collectFrameRate}, 帧时间={config.collectFrameTime}, CPU={config.collectCpuUsage}, GPU={config.collectGpuUsage}, 内存={config.collectMemory}, 设备={config.collectDeviceInfo}, " +
                $"质量项 光照={config.testLightingQuality}, 材质={config.testMaterialQuality}, 后处理={config.testPostProcessingQuality}, 物理={config.testPhysicsQuality}"
            );
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
            public bool enableNetworkUpload;
            public bool autoCreateSession;
            public bool autoStart;
            public bool quitOnComplete;
            public XRBatchQualityChecks qualityChecks;
            public XRBatchQualityMetricChecks qualityMetricChecks;
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

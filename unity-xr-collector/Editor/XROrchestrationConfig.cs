using System;
using UnityEngine;

namespace XRDataCollector.Editor
{
    [Serializable]
    public class XROrchestrationTaskConfig
    {
        public const int SupportedSchemaVersion = 1;
        public const string RunModeMultiScene = "multi_scene";

        public int schemaVersion = SupportedSchemaVersion;
        public string runMode = RunModeMultiScene;
        public int batchId;
        public int parentTaskId;
        public int projectId;
        public string unityProjectPath;
        public string progressUrl;
        public string deviceToken;
        public bool quitOnComplete;
        public XRSceneRunConfig[] scenes;
    }

    [Serializable]
    public class XRSceneRunConfig
    {
        public int batchItemId;
        public int sceneIndex;
        public int sceneTotal;
        public int attempt = 1;
        public int taskId;
        public int platformSessionId;
        public string sessionName;
        public int sceneId;
        public string projectName;
        public string platformBaseUrl;
        public string unityScenePath;
        public string uploadUrl;
        public string progressUrl;
        public float collectInterval = 1f;
        public float frameRateDurationSeconds = 30f;
        public float metricsDurationSeconds = 30f;
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
        public bool enableNetworkUpload = true;
        public bool autoCreateSession;
        public bool autoStart;
        public bool forceAutoFlythroughOnStart = true;
        public string sceneDisplayName;
        public XROrchestrationQualityChecks qualityChecks;
        public XROrchestrationQualityMetricChecks qualityMetricChecks;
    }

    [Serializable]
    public class XROrchestrationCommandFile
    {
        public const int SupportedSchemaVersion = 1;

        public int schemaVersion = SupportedSchemaVersion;
        public string commandId;
        public int batchId;
        public int expectedBatchItemId;
        public int expectedSceneIndex;
        public int decisionVersion;
        public string action;
        public XRSceneRunConfig retrySceneConfig;
    }

    [Serializable]
    public class XROrchestrationQualityChecks
    {
        public bool lighting = true;
        public bool materials = true;
        public bool postProcessing = true;
        public bool physics = true;
    }

    [Serializable]
    public class XROrchestrationQualityMetricChecks
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

    [Serializable]
    internal class XROrchestrationRunModeProbe
    {
        public string runMode;
        public int schemaVersion;
    }

    public static class XROrchestrationConfigParser
    {
        public static bool IsMultiSceneConfig(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
                return false;

            var probe = JsonUtility.FromJson<XROrchestrationRunModeProbe>(json);
            return probe != null &&
                   string.Equals(probe.runMode, XROrchestrationTaskConfig.RunModeMultiScene, StringComparison.OrdinalIgnoreCase);
        }

        public static bool TryParse(string json, out XROrchestrationTaskConfig config, out string error)
        {
            config = null;
            error = null;

            if (string.IsNullOrWhiteSpace(json))
            {
                error = "编排配置为空。";
                return false;
            }

            config = JsonUtility.FromJson<XROrchestrationTaskConfig>(json);
            if (config == null)
            {
                error = "编排配置解析失败。";
                return false;
            }

            if (config.schemaVersion != XROrchestrationTaskConfig.SupportedSchemaVersion)
            {
                error = $"不支持的编排 schemaVersion={config.schemaVersion}，当前仅支持 {XROrchestrationTaskConfig.SupportedSchemaVersion}。";
                return false;
            }

            if (!string.Equals(config.runMode, XROrchestrationTaskConfig.RunModeMultiScene, StringComparison.OrdinalIgnoreCase))
            {
                error = $"不支持的 runMode={config.runMode}。";
                return false;
            }

            if (config.scenes == null || config.scenes.Length == 0)
            {
                error = "编排配置缺少 scenes。";
                return false;
            }

            return true;
        }
    }
}

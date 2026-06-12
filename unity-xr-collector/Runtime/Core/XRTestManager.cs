using System;
using System.Collections.Generic;
using UnityEngine;
using XRDataCollector.Collectors;
using XRDataCollector.Data;
using XRDataCollector.Exporters;
using XRDataCollector.Network;

namespace XRDataCollector.Core
{
    public class XRTestManager : MonoBehaviour
    {
        #region Singleton

        public static XRTestManager Instance { get; private set; }

        internal static void ResetDomainState()
        {
            Instance = null;
        }

        #endregion

        #region Events

        public event Action<PerformanceSample> OnSampleCollected;
        public event Action OnSessionStarted;
        public event Action OnSessionStopped;
        public event Action<string> OnDataExported;
        public event Action<bool> OnDataUploaded;
        public event Action<int> OnPlatformSessionCreated;

        #endregion

        #region Fields

        private enum CollectionPhase
        {
            None,
            FrameRate,
            Metrics
        }

        private const string FrameRatePhaseName = "frame_rate";
        private const string MetricsPhaseName = "metrics";

        [SerializeField]
        private XRTestConfig config;

        private XRTestSession session;
        private List<IPerformanceCollector> allCollectors;
        private List<IPerformanceCollector> batchCollectors;
        private List<IPerformanceCollector> liveCollectors;
        private List<PerformanceSample> samples;
        private float collectTimer;
        private bool isCollecting;
        private bool isPlatformSessionCreating;
        private bool pendingUploadAfterPlatformSession;

        private FrameRateCollector frameRateCollector;
        private FrameTimeCollector frameTimeCollector;
        private RenderingStatsCollector renderingStatsCollector;
        private float cachedFrameRate;
        private float cachedFrameTimeMs;
        private int lastBatchFrameCount;
        private float lastBatchRealTime;
        private float collectionStartRealTime;
        private CollectionPhase currentPhase;

        #endregion

        #region Properties

        public bool IsCollecting => isCollecting;

        public XRTestConfig Config
        {
            get
            {
                EnsureRuntimeState();
                return config;
            }
        }

        public XRTestSession Session => session;
        public int PlatformSessionId => session != null ? session.PlatformSessionId : 0;

        private float FrameRatePhaseDurationSeconds => Mathf.Max(1f, config != null ? config.frameRateDurationSeconds : 30f);
        private float MetricsPhaseDurationSeconds => Mathf.Max(1f, config != null ? config.metricsDurationSeconds : 30f);

        public string CurrentCollectionPhase
        {
            get
            {
                switch (currentPhase)
                {
                    case CollectionPhase.FrameRate:
                        return "帧率采集 (0-30秒)";
                    case CollectionPhase.Metrics:
                        return "指标采集 (30-60秒)";
                    default:
                        return "空闲";
                }
            }
        }

        public float CurrentPhaseRemainingSeconds
        {
            get
            {
                if (!isCollecting) return 0f;
                float elapsed = Time.unscaledTime - collectionStartRealTime;
                if (currentPhase == CollectionPhase.FrameRate)
                    return Mathf.Max(0f, FrameRatePhaseDurationSeconds - elapsed);
                if (currentPhase == CollectionPhase.Metrics)
                    return Mathf.Max(0f, FrameRatePhaseDurationSeconds + MetricsPhaseDurationSeconds - elapsed);
                return 0f;
            }
        }

        /// <summary>
        /// 总采集进度（0~1），用于窗口进度条显示
        /// </summary>
        public float CollectionProgress
        {
            get
            {
                if (!isCollecting) return 0f;
                float totalDuration = FrameRatePhaseDurationSeconds + MetricsPhaseDurationSeconds;
                float elapsed = Time.unscaledTime - collectionStartRealTime;
                return Mathf.Clamp01(elapsed / totalDuration);
            }
        }

        #endregion

        #region Unity Lifecycle

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
#if !UNITY_EDITOR
            DontDestroyOnLoad(gameObject);
#endif
            EnsureRuntimeState();
        }

#if UNITY_EDITOR
        private void OnEnable()
        {
            if (!isCollecting)
                return;
            if (string.IsNullOrEmpty(UnityEditor.SessionState.GetString("XRDataCollector.PendingTaskConfigJson", string.Empty)))
                return;
            if (batchCollectors == null || batchCollectors.Count == 0)
                InitializeCollectors();
            RestoreCollectorStateForPhase(currentPhase);
            if (config != null && config.forceAutoFlythroughOnStart)
                TestSceneFlythroughActivator.RequestActivation(this);
        }
#endif

        private void Start()
        {
            EnsureRuntimeState();
#if UNITY_EDITOR
            // 网页冷启动 / 脚本域重载：采集生命周期由 XRBatchTestRunner 接管，避免 Start 重建采集器导致指标归零。
            if (!string.IsNullOrEmpty(UnityEditor.SessionState.GetString("XRDataCollector.PendingTaskConfigJson", string.Empty)))
                return;
#endif
            InitializeCollectors();
            if (config.autoStart)
                StartCollection();
        }

        private void Update()
        {
            if (!isCollecting) return;

            float collectionElapsed = Time.unscaledTime - collectionStartRealTime;
            if (currentPhase == CollectionPhase.FrameRate && collectionElapsed >= FrameRatePhaseDurationSeconds)
                SwitchToMetricsPhase();

            if (currentPhase == CollectionPhase.Metrics &&
                collectionElapsed >= FrameRatePhaseDurationSeconds + MetricsPhaseDurationSeconds)
            {
                StopCollection();
                return;
            }

            int currentFrameCount = Time.frameCount;
            float currentTime = Time.unscaledTime;
            int framesPassed = currentFrameCount - lastBatchFrameCount;
            float timePassed = currentTime - lastBatchRealTime;

            if (framesPassed > 0 && timePassed > 0f)
                cachedFrameRate = framesPassed / timePassed;
            else if (Time.unscaledDeltaTime > 0f)
                cachedFrameRate = 1f / Time.unscaledDeltaTime;

            cachedFrameTimeMs = Time.unscaledDeltaTime * 1000f;
            collectTimer += Time.unscaledDeltaTime;

            if (collectTimer >= config.collectInterval)
            {
                collectTimer = 0f;
                if (currentPhase == CollectionPhase.FrameRate)
                    CollectFrameRateSample();
                else if (currentPhase == CollectionPhase.Metrics)
                    CollectMetricsSample();
                lastBatchFrameCount = Time.frameCount;
                lastBatchRealTime = Time.unscaledTime;
            }
        }

        private void OnDestroy()
        {
            if (isCollecting)
                StopCollection(uploadResults: false);
            else
                DisposeAllCollectors();

            if (Instance == this) Instance = null;
        }

        #endregion

        #region Public Methods

        public void Initialize(XRTestConfig newConfig)
        {
            config = newConfig ?? new XRTestConfig();
            EnsureRuntimeState();
            bool wasCollecting = isCollecting;
            var phase = currentPhase;
            InitializeCollectors();
            if (wasCollecting)
                RestoreCollectorStateForPhase(phase);
        }

        /// <summary>
        /// 脚本热重载后恢复采集器，避免 CPU/GPU/内存等指标在首个样本后归零。
        /// </summary>
        public void EnsureCollectorsActiveAfterReload()
        {
            if (!isCollecting)
                return;

            RestoreCollectorStateForPhase(currentPhase);
            if (config.forceAutoFlythroughOnStart)
                TestSceneFlythroughActivator.RequestActivation(this);
            Debug.Log($"[XRTestManager] 采集器已恢复，阶段={currentPhase}，batch={batchCollectors.Count}，live={liveCollectors.Count}。");
        }

        public void StartCollection()
        {
            EnsureRuntimeState();
            if (allCollectors.Count == 0) InitializeCollectors();
            if (isCollecting) return;

            // Multi-scene runs can reuse this manager when Enter Play Mode has
            // scene reload disabled. PrepareForShutdown disables it after the
            // previous scene, so restore Update before starting the next run.
            enabled = true;

            if (config.enableNetworkUpload)
                TestDataUploader.EnsureRuntimeHost();

            session = new XRTestSession(config.sessionName);
            session.Start();
            if (config.platformSessionId > 0)
                session.BindPlatformSession(config.platformSessionId, 0, config.sessionName);
            samples.Clear();
            collectTimer = 0f;
            isCollecting = true;
            isPlatformSessionCreating = false;
            pendingUploadAfterPlatformSession = false;
            cachedFrameRate = 0f;
            cachedFrameTimeMs = 0f;
            lastBatchFrameCount = Time.frameCount;
            lastBatchRealTime = Time.unscaledTime;
            collectionStartRealTime = Time.unscaledTime;
            foreach (var collector in liveCollectors)
                collector.StartCollecting();
            StartFrameRatePhase();
            EnsureProgressReporter();

            if (config.forceAutoFlythroughOnStart)
                TestSceneFlythroughActivator.RequestActivation(this);

            OnSessionStarted?.Invoke();
            CreatePlatformSessionForCurrentRun();
            Debug.Log(
                $"[XRTestManager] 会话 '{config.sessionName}' 已开始。阶段1时长={config.frameRateDurationSeconds:F1}s，" +
                $"阶段2时长={config.metricsDurationSeconds:F1}s，间隔={config.collectInterval:F2}s，" +
                $"CPU={config.collectCpuUsage}, GPU={config.collectGpuUsage}, 内存={config.collectMemory}, 设备={config.collectDeviceInfo}。");
        }

        public void StopCollection(bool uploadResults = true)
        {
            if (!isCollecting) return;
            isCollecting = false;
            session?.Stop();

            foreach (var collector in allCollectors)
                collector.StopCollecting();

            currentPhase = CollectionPhase.None;
            OnSessionStopped?.Invoke();
            Debug.Log($"[XRTestManager] 会话 '{config.sessionName}' 已停止。共采集样本数：{samples.Count}");

            if (uploadResults && config.enableNetworkUpload)
            {
                if (samples.Count > 0)
                    UploadData("", null);
                else
                {
                    Debug.LogError("[XRTestManager] 采集结束但没有生成任何样本，无法上传。");
                    NotifyDataUploaded(false);
                }
            }
        }

        public void ExportData(IDataExporter exporter, string filePath)
        {
            if (exporter == null)
            {
                Debug.LogError("[XRTestManager] 导出器为空。");
                return;
            }
            if (samples.Count == 0)
            {
                Debug.LogWarning("[XRTestManager] 没有可导出的样本。");
                return;
            }
            try
            {
                exporter.Export(samples, session, filePath);
                OnDataExported?.Invoke(filePath);
                Debug.Log($"[XRTestManager] 数据已导出至：{filePath}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[XRTestManager] 导出失败：{e.Message}");
            }
        }

        public void UploadData(string url, string authToken = null)
        {
            if (samples.Count == 0)
            {
                Debug.LogWarning("[XRTestManager] 没有可上传的样本。");
                OnDataUploaded?.Invoke(false);
                return;
            }

            if (string.IsNullOrEmpty(url) && config != null && config.autoCreateSession &&
                session != null && session.PlatformSessionId <= 0 && isPlatformSessionCreating)
            {
                pendingUploadAfterPlatformSession = true;
                Debug.Log("[XRTestManager] 平台会话正在创建中，上传将在就绪后继续。");
                return;
            }

            var uploader = new TestDataUploader();
            if (string.IsNullOrEmpty(url))
            {
                EnsureRuntimeState();
                uploader.UploadAsync(samples, session, config, NotifyDataUploaded);
                return;
            }

            string token = string.IsNullOrEmpty(authToken) ? config?.deviceToken : authToken;
            uploader.UploadAsync(samples, session, url, token, NotifyDataUploaded);
        }

        public PerformanceSample GetLatestSample()
        {
            if (samples.Count == 0) return null;
            return samples[samples.Count - 1];
        }

        public List<PerformanceSample> GetAllSamples()
        {
            return new List<PerformanceSample>(samples);
        }

        public int GetSampleCount() => samples.Count;

        public void ClearSamples() => samples.Clear();

        /// <summary>
        /// 构建用于实时进度上报的当前快照，确保前端展示字段持续更新。
        /// </summary>
        public PerformanceSample BuildLiveProgressSample()
        {
            var sample = CreateBaseSample(
                currentPhase == CollectionPhase.FrameRate ? FrameRatePhaseName : MetricsPhaseName);

            sample.frameRate = cachedFrameRate;
            sample.frameTimeMs = cachedFrameTimeMs;
            sample.rawFrameTimeMs = cachedFrameTimeMs;

            if (liveCollectors != null)
            {
                foreach (var collector in liveCollectors)
                    collector.Collect(ref sample);
            }

            return sample;
        }

        #endregion

        #region Private Methods

        private void EnsureProgressReporter()
        {
            if (string.IsNullOrEmpty(config.progressUrl)) return;
            var reporter = GetComponent<UnityProgressReporter>();
            if (reporter == null)
                reporter = gameObject.AddComponent<UnityProgressReporter>();
            reporter.enabled = true;
            reporter.Initialize(this);
        }

        private void CreatePlatformSessionForCurrentRun()
        {
            EnsureRuntimeState();
            if (!config.enableNetworkUpload || !config.autoCreateSession || config.projectId <= 0 || session == null)
                return;

            var targetSession = session;
            isPlatformSessionCreating = true;

            var uploader = new TestDataUploader();
            uploader.CreatePlatformSessionAsync(config, targetSession, (sessionId, runIndex, platformName, error) =>
            {
                isPlatformSessionCreating = false;
                if (targetSession != session) return;

                if (sessionId > 0)
                {
                    targetSession.BindPlatformSession(sessionId, runIndex, platformName);
                    OnPlatformSessionCreated?.Invoke(sessionId);
                    Debug.Log($"[XRTestManager] 平台会话已创建：{sessionId}，运行 #{runIndex}。");
                }
                else if (!string.IsNullOrEmpty(error))
                {
                    Debug.LogError($"[XRTestManager] 平台会话创建失败：{error}");
                }

                if (pendingUploadAfterPlatformSession && samples.Count > 0)
                {
                    pendingUploadAfterPlatformSession = false;
                    UploadData("", null);
                }
            });
        }

        private void NotifyDataUploaded(bool success)
        {
            PrepareForShutdown();
            OnDataUploaded?.Invoke(success);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.delayCall += () => Network.TestDataUploader.DestroyInstance();
#endif
        }

        /// <summary>
        /// 上传完成后的清理：停止实时上报与巡航，降低退出 Play Mode / Editor 时崩溃概率。
        /// </summary>
        public void PrepareForShutdown()
        {
            enabled = false;

            var reporter = GetComponent<UnityProgressReporter>();
            if (reporter != null)
                reporter.enabled = false;

            try
            {
                TestSceneFlythroughActivator.StopPresentation();
            }
            catch (Exception exception)
            {
                Debug.LogWarning("[XRTestManager] 停止场景演示失败，已忽略并继续关闭：" + exception.Message);
            }
        }

        private void DisposeAllCollectors()
        {
            if (allCollectors == null)
                return;

            foreach (var collector in allCollectors)
                collector.StopCollecting();
        }

        private void InitializeCollectors()
        {
            EnsureRuntimeState();
            DisposeAllCollectors();
            allCollectors.Clear();
            batchCollectors.Clear();

            frameRateCollector = new FrameRateCollector();
            frameTimeCollector = new FrameTimeCollector();
            renderingStatsCollector = new RenderingStatsCollector();
            var cpuCollector = new CpuUsageCollector();
            var gpuCollector = new GpuUsageCollector();
            var memoryCollector = new MemoryCollector();
            var deviceCollector = new DeviceInfoCollector();
            var renderQualityCollector = new RenderQualityCollector(config);
            var resourceMemoryCollector = new ResourceMemoryCollector(config);

            if (config.collectFrameRate)
                allCollectors.Add(frameRateCollector);
            if (config.collectFrameTime)
                allCollectors.Add(frameTimeCollector);
            if (config.collectCpuUsage)
                allCollectors.Add(cpuCollector);
            if (config.collectGpuUsage)
                allCollectors.Add(gpuCollector);
            if (config.collectMemory)
                allCollectors.Add(memoryCollector);
            if (config.collectDeviceInfo)
                allCollectors.Add(deviceCollector);
            if (config.collectRenderingStats)
                allCollectors.Add(renderingStatsCollector);
            if (config.collectRenderQuality)
                allCollectors.Add(renderQualityCollector);
            if (config.collectMemory || config.collectRenderQuality)
                allCollectors.Add(resourceMemoryCollector);

            if (config.collectCpuUsage)
                batchCollectors.Add(cpuCollector);
            if (config.collectGpuUsage)
                batchCollectors.Add(gpuCollector);
            if (config.collectMemory)
                batchCollectors.Add(memoryCollector);
            if (config.collectDeviceInfo)
                batchCollectors.Add(deviceCollector);
            if (config.collectRenderingStats)
                batchCollectors.Add(renderingStatsCollector);
            if (config.collectRenderQuality)
                batchCollectors.Add(renderQualityCollector);
            if (config.collectMemory || config.collectRenderQuality)
                batchCollectors.Add(resourceMemoryCollector);

            liveCollectors.Clear();
            if (config.collectCpuUsage)
                liveCollectors.Add(cpuCollector);
            if (config.collectGpuUsage)
                liveCollectors.Add(gpuCollector);
            if (config.collectMemory)
                liveCollectors.Add(memoryCollector);
            if (config.collectDeviceInfo)
            {
                liveCollectors.Add(deviceCollector);
            }
            if (config.collectRenderingStats)
                liveCollectors.Add(renderingStatsCollector);
            if (config.collectRenderQuality)
                liveCollectors.Add(renderQualityCollector);
            if (config.collectMemory || config.collectRenderQuality)
                liveCollectors.Add(resourceMemoryCollector);
        }

        private void Reset() => EnsureRuntimeState();
        private void OnValidate() => EnsureRuntimeState();

        private void EnsureRuntimeState()
        {
            if (config == null) config = new XRTestConfig();
            config.NormalizeRuntimeSettings();
            if (allCollectors == null) allCollectors = new List<IPerformanceCollector>();
            if (batchCollectors == null) batchCollectors = new List<IPerformanceCollector>();
            if (liveCollectors == null) liveCollectors = new List<IPerformanceCollector>();
            if (samples == null) samples = new List<PerformanceSample>();
        }

        private void StartFrameRatePhase()
        {
            currentPhase = CollectionPhase.FrameRate;
            if (config.collectFrameRate)
                frameRateCollector?.StartCollecting();
            if (config.collectFrameTime)
                frameTimeCollector?.StartCollecting();
            StartBatchMetricCollectors();
        }

        private void StartBatchMetricCollectors()
        {
            foreach (var collector in batchCollectors)
                collector.StartCollecting();
        }

        private void RestoreCollectorStateForPhase(CollectionPhase phase)
        {
            if (!isCollecting || phase == CollectionPhase.None)
                return;

            if (phase == CollectionPhase.FrameRate)
            {
                if (config.collectFrameRate)
                    frameRateCollector?.StartCollecting();
                if (config.collectFrameTime)
                    frameTimeCollector?.StartCollecting();
            }

            StartBatchMetricCollectors();

            if (liveCollectors != null)
            {
                foreach (var collector in liveCollectors)
                    collector.StartCollecting();
            }
        }

        private void AppendBatchMetrics(ref PerformanceSample sample)
        {
            foreach (var collector in batchCollectors)
                collector.Collect(ref sample);
        }

        private void SwitchToMetricsPhase()
        {
            frameRateCollector?.StopCollecting();
            frameTimeCollector?.StopCollecting();

            currentPhase = CollectionPhase.Metrics;
            collectTimer = 0f;
            lastBatchFrameCount = Time.frameCount;
            lastBatchRealTime = Time.unscaledTime;
            Debug.Log("[XRTestManager] 阶段2已开始：采集其他指标（非帧率），时长30秒。");
        }

        private PerformanceSample CreateBaseSample(string phase)
        {
            return new PerformanceSample
            {
                timestamp = DateTime.UtcNow,
                sessionId = session?.SessionId ?? "unknown",
                elapsedTime = session?.ElapsedTime ?? TimeSpan.Zero,
                collectionPhase = phase
            };
        }

        private void CollectFrameRateSample()
        {
            var sample = CreateBaseSample(FrameRatePhaseName);
            AppendFrameMetrics(ref sample);
            AppendBatchMetrics(ref sample);
            samples.Add(sample);
            OnSampleCollected?.Invoke(sample);
            LogSampleSummary(sample);
        }

        private void CollectMetricsSample()
        {
            var sample = CreateBaseSample(MetricsPhaseName);
            AppendFrameMetrics(ref sample);
            AppendBatchMetrics(ref sample);
            samples.Add(sample);
            OnSampleCollected?.Invoke(sample);
            LogSampleSummary(sample);
        }

        private void AppendFrameMetrics(ref PerformanceSample sample)
        {
            if (config.collectFrameRate)
                sample.frameRate = cachedFrameRate;
            if (config.collectFrameTime)
            {
                sample.frameTimeMs = cachedFrameTimeMs;
                sample.rawFrameTimeMs = cachedFrameTimeMs;
            }
        }

        private void LogSampleSummary(PerformanceSample sample)
        {
            bool verbose = config != null && config.enableNetworkUpload;
            if (!verbose && samples.Count != 1 && samples.Count % 10 != 0)
                return;
            if (verbose && samples.Count != 1 && samples.Count % 5 != 0)
                return;

            Debug.Log(
                $"[XRTestManager] 样本 #{samples.Count} ({sample.collectionPhase})：" +
                $"FPS={sample.frameRate:F1}, 帧时={sample.frameTimeMs:F2}ms, " +
                $"CPU={sample.cpuUsagePercent:F1}%, GPU={sample.gpuUsagePercent:F1}%, " +
                $"内存={sample.totalMemoryMB:F1}MB, 托管={sample.managedMemoryMB:F1}MB, 显存={sample.graphicsMemoryMB:F1}MB, " +
                $"DrawCalls={sample.drawCalls}, Triangles={sample.triangles}, Vertices={sample.vertices}, " +
                $"光源={sample.activeLightCount}/{sample.realtimeLightCount}, 阴影={sample.shadowCasterCount}, " +
                $"材质={sample.materialCount}, 设备信息={(sample.deviceInfo != null ? "有" : "无")}。");
        }

        #endregion
    }
}

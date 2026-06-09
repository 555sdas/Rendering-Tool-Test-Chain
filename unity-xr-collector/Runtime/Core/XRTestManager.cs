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
        private List<PerformanceSample> samples;
        private float collectTimer;
        private bool isCollecting;
        private bool isPlatformSessionCreating;
        private bool pendingUploadAfterPlatformSession;

        private FrameRateCollector frameRateCollector;
        private FrameTimeCollector frameTimeCollector;
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
            DontDestroyOnLoad(gameObject);
            EnsureRuntimeState();
        }

        private void Start()
        {
            EnsureRuntimeState();
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
            if (isCollecting) StopCollection();
            if (Instance == this) Instance = null;
        }

        #endregion

        #region Public Methods

        public void Initialize(XRTestConfig newConfig)
        {
            config = newConfig ?? new XRTestConfig();
            EnsureRuntimeState();
            InitializeCollectors();
        }

        public void StartCollection()
        {
            EnsureRuntimeState();
            if (allCollectors.Count == 0) InitializeCollectors();
            if (isCollecting) return;

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
            StartFrameRatePhase();

            OnSessionStarted?.Invoke();
            CreatePlatformSessionForCurrentRun();
            Debug.Log($"[XRTestManager] 会话 '{config.sessionName}' 已开始。阶段1：前30秒采集帧率。");
        }

        public void StopCollection()
        {
            if (!isCollecting) return;
            isCollecting = false;
            session?.Stop();

            foreach (var collector in allCollectors)
                collector.StopCollecting();

            currentPhase = CollectionPhase.None;
            OnSessionStopped?.Invoke();
            Debug.Log($"[XRTestManager] 会话 '{config.sessionName}' 已停止。共采集样本数：{samples.Count}");

            if (config.enableNetworkUpload && samples.Count > 0)
                UploadData("", null);
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

        #endregion

        #region Private Methods

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
            OnDataUploaded?.Invoke(success);
            QuitAfterCommandLineRun(success);
        }

        private void QuitAfterCommandLineRun(bool success)
        {
            if (config == null || !config.quitOnComplete) return;

#if UNITY_EDITOR
            UnityEditor.EditorApplication.delayCall += () =>
            {
                if (UnityEditor.EditorApplication.isPlaying)
                    UnityEditor.EditorApplication.isPlaying = false;
                UnityEditor.EditorApplication.Exit(success ? 0 : 1);
            };
#else
            Application.Quit(success ? 0 : 1);
#endif
        }

        private void InitializeCollectors()
        {
            EnsureRuntimeState();
            allCollectors.Clear();
            batchCollectors.Clear();

            frameRateCollector = new FrameRateCollector();
            frameTimeCollector = new FrameTimeCollector();
            var cpuCollector = new CpuUsageCollector();
            var gpuCollector = new GpuUsageCollector();
            var memoryCollector = new MemoryCollector();
            var deviceCollector = new DeviceInfoCollector();
            var renderQualityCollector = new RenderQualityCollector(config);

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
            allCollectors.Add(renderQualityCollector);

            if (config.collectCpuUsage)
                batchCollectors.Add(cpuCollector);
            if (config.collectGpuUsage)
                batchCollectors.Add(gpuCollector);
            if (config.collectMemory)
                batchCollectors.Add(memoryCollector);
            if (config.collectDeviceInfo)
                batchCollectors.Add(deviceCollector);
            batchCollectors.Add(renderQualityCollector);
        }

        private void Reset() => EnsureRuntimeState();
        private void OnValidate() => EnsureRuntimeState();

        private void EnsureRuntimeState()
        {
            if (config == null) config = new XRTestConfig();
            config.NormalizeRuntimeSettings();
            if (allCollectors == null) allCollectors = new List<IPerformanceCollector>();
            if (batchCollectors == null) batchCollectors = new List<IPerformanceCollector>();
            if (samples == null) samples = new List<PerformanceSample>();
        }

        private void StartFrameRatePhase()
        {
            currentPhase = CollectionPhase.FrameRate;
            if (config.collectFrameRate)
                frameRateCollector?.StartCollecting();
            if (config.collectFrameTime)
                frameTimeCollector?.StartCollecting();
        }

        private void SwitchToMetricsPhase()
        {
            frameRateCollector?.StopCollecting();
            frameTimeCollector?.StopCollecting();
            foreach (var collector in batchCollectors)
                collector.StartCollecting();

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
            if (config.collectFrameRate)
                sample.frameRate = cachedFrameRate;
            if (config.collectFrameTime)
            {
                sample.frameTimeMs = cachedFrameTimeMs;
                sample.rawFrameTimeMs = cachedFrameTimeMs;
            }
            samples.Add(sample);
            OnSampleCollected?.Invoke(sample);
        }

        private void CollectMetricsSample()
        {
            var sample = CreateBaseSample(MetricsPhaseName);
            foreach (var collector in batchCollectors)
                collector.Collect(ref sample);
            samples.Add(sample);
            OnSampleCollected?.Invoke(sample);
        }

        #endregion
    }
}

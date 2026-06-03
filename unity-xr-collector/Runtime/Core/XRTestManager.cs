using System;
using System.Collections.Generic;
using UnityEngine;
using XRDataCollector.Collectors;
using XRDataCollector.Data;
using XRDataCollector.Exporters;
using XRDataCollector.Network;

namespace XRDataCollector.Core
{
    /// <summary>
    /// XR 测试数据管理器主类
    /// 负责协调所有采集器、管理测试会话、处理数据导出和上传
    /// </summary>
    public class XRTestManager : MonoBehaviour
    {
        #region Singleton

        public static XRTestManager Instance { get; private set; }

        #endregion

        #region Events

        /// <summary>
        /// 当新的性能样本采集完成时触发
        /// </summary>
        public event Action<PerformanceSample> OnSampleCollected;

        /// <summary>
        /// 当测试会话开始时触发
        /// </summary>
        public event Action OnSessionStarted;

        /// <summary>
        /// 当测试会话停止时触发
        /// </summary>
        public event Action OnSessionStopped;

        /// <summary>
        /// 当数据导出完成时触发
        /// </summary>
        public event Action<string> OnDataExported;

        /// <summary>
        /// 当数据上传完成时触发，参数为是否成功
        /// </summary>
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

        private const float FrameRatePhaseDurationSeconds = 30f;
        private const float MetricsPhaseDurationSeconds = 30f;
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

        /// <summary>
        /// 当前是否正在采集数据
        /// </summary>
        public bool IsCollecting => isCollecting;

        /// <summary>
        /// 当前配置
        /// </summary>
        public XRTestConfig Config
        {
            get
            {
                EnsureRuntimeState();
                return config;
            }
        }

        /// <summary>
        /// 当前会话信息
        /// </summary>
        public XRTestSession Session => session;

        public int PlatformSessionId => session != null ? session.PlatformSessionId : 0;

        /// <summary>
        /// 当前采集阶段
        /// </summary>
        public string CurrentCollectionPhase
        {
            get
            {
                switch (currentPhase)
                {
                    case CollectionPhase.FrameRate:
                        return "Frame Rate (0-30s)";
                    case CollectionPhase.Metrics:
                        return "Metrics (30-60s)";
                    default:
                        return "Idle";
                }
            }
        }

        /// <summary>
        /// 当前阶段剩余秒数
        /// </summary>
        public float CurrentPhaseRemainingSeconds
        {
            get
            {
                if (!isCollecting) return 0f;

                float elapsed = Time.unscaledTime - collectionStartRealTime;
                if (currentPhase == CollectionPhase.FrameRate)
                {
                    return Mathf.Max(0f, FrameRatePhaseDurationSeconds - elapsed);
                }

                if (currentPhase == CollectionPhase.Metrics)
                {
                    return Mathf.Max(0f, FrameRatePhaseDurationSeconds + MetricsPhaseDurationSeconds - elapsed);
                }

                return 0f;
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
            {
                StartCollection();
            }
        }

        private void Update()
        {
            if (!isCollecting) return;

            float collectionElapsed = Time.unscaledTime - collectionStartRealTime;
            if (currentPhase == CollectionPhase.FrameRate && collectionElapsed >= FrameRatePhaseDurationSeconds)
            {
                SwitchToMetricsPhase();
            }

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
            {
                cachedFrameRate = framesPassed / timePassed;
            }
            else if (Time.unscaledDeltaTime > 0f)
            {
                cachedFrameRate = 1f / Time.unscaledDeltaTime;
            }

            cachedFrameTimeMs = Time.unscaledDeltaTime * 1000f;

            collectTimer += Time.unscaledDeltaTime;

            if (collectTimer >= config.collectInterval)
            {
                collectTimer = 0f;

                if (currentPhase == CollectionPhase.FrameRate)
                {
                    CollectFrameRateSample();
                }
                else if (currentPhase == CollectionPhase.Metrics)
                {
                    CollectMetricsSample();
                }

                lastBatchFrameCount = Time.frameCount;
                lastBatchRealTime = Time.unscaledTime;
            }
        }

        private void OnDestroy()
        {
            if (isCollecting)
            {
                StopCollection();
            }

            if (Instance == this)
            {
                Instance = null;
            }
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// 使用指定配置初始化管理器
        /// </summary>
        /// <param name="newConfig">测试配置</param>
        public void Initialize(XRTestConfig newConfig)
        {
            config = newConfig ?? new XRTestConfig();
            EnsureRuntimeState();
            InitializeCollectors();
        }

        /// <summary>
        /// 开始数据采集
        /// </summary>
        public void StartCollection()
        {
            EnsureRuntimeState();
            if (allCollectors.Count == 0)
            {
                InitializeCollectors();
            }
            if (isCollecting) return;

            session = new XRTestSession(config.sessionName);
            session.Start();

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
            Debug.Log($"[XRTestManager] Session '{config.sessionName}' started. Phase 1: frame rate for 30s.");
        }

        /// <summary>
        /// 停止数据采集
        /// </summary>
        public void StopCollection()
        {
            if (!isCollecting) return;

            isCollecting = false;
            session?.Stop();

            foreach (var collector in allCollectors)
            {
                collector.StopCollecting();
            }

            currentPhase = CollectionPhase.None;

            OnSessionStopped?.Invoke();
            Debug.Log($"[XRTestManager] Session '{config.sessionName}' stopped. Samples collected: {samples.Count}");

            if (config.enableNetworkUpload && samples.Count > 0)
            {
                UploadData("", null);
            }
        }

        /// <summary>
        /// 使用指定导出器导出数据
        /// </summary>
        /// <param name="exporter">数据导出器</param>
        /// <param name="filePath">导出文件路径</param>
        public void ExportData(IDataExporter exporter, string filePath)
        {
            if (exporter == null)
            {
                Debug.LogError("[XRTestManager] Exporter is null.");
                return;
            }

            if (samples.Count == 0)
            {
                Debug.LogWarning("[XRTestManager] No samples to export.");
                return;
            }

            try
            {
                exporter.Export(samples, session, filePath);
                OnDataExported?.Invoke(filePath);
                Debug.Log($"[XRTestManager] Data exported to: {filePath}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[XRTestManager] Export failed: {e.Message}");
            }
        }

        /// <summary>
        /// 上传数据到指定服务器
        /// </summary>
        /// <param name="url">上传地址</param>
        public void UploadData(string url, string authToken = null)
        {
            if (samples.Count == 0)
            {
                Debug.LogWarning("[XRTestManager] No samples to upload.");
                OnDataUploaded?.Invoke(false);
                return;
            }

            if (string.IsNullOrEmpty(url) &&
                config != null &&
                config.autoCreateSession &&
                session != null &&
                session.PlatformSessionId <= 0 &&
                isPlatformSessionCreating)
            {
                pendingUploadAfterPlatformSession = true;
                Debug.Log("[XRTestManager] Platform session is still being created. Upload will continue after it is ready.");
                return;
            }

            var uploader = new TestDataUploader();
            if (string.IsNullOrEmpty(url))
            {
                EnsureRuntimeState();
                uploader.UploadAsync(samples, session, config, success =>
                {
                    OnDataUploaded?.Invoke(success);
                });
                return;
            }

            string token = string.IsNullOrEmpty(authToken) ? config?.authToken : authToken;
            uploader.UploadAsync(samples, session, url, token, success =>
            {
                OnDataUploaded?.Invoke(success);
            });
        }

        /// <summary>
        /// 获取最新的性能样本
        /// </summary>
        /// <returns>最新样本，如果没有则返回 null</returns>
        public PerformanceSample GetLatestSample()
        {
            if (samples.Count == 0) return null;
            return samples[samples.Count - 1];
        }

        /// <summary>
        /// 获取所有采集的样本（副本）
        /// </summary>
        /// <returns>样本列表副本</returns>
        public List<PerformanceSample> GetAllSamples()
        {
            return new List<PerformanceSample>(samples);
        }

        /// <summary>
        /// 获取样本数量
        /// </summary>
        /// <returns>已采集的样本总数</returns>
        public int GetSampleCount()
        {
            return samples.Count;
        }

        /// <summary>
        /// 清除所有已采集的样本
        /// </summary>
        public void ClearSamples()
        {
            samples.Clear();
        }

        #endregion

        #region Private Methods

        private void CreatePlatformSessionForCurrentRun()
        {
            EnsureRuntimeState();
            if (!config.enableNetworkUpload || !config.autoCreateSession || config.projectId <= 0 || session == null)
            {
                return;
            }

            var targetSession = session;
            isPlatformSessionCreating = true;

            var uploader = new TestDataUploader();
            uploader.CreatePlatformSessionAsync(config, targetSession, (sessionId, runIndex, platformName, error) =>
            {
                isPlatformSessionCreating = false;

                if (targetSession != session)
                {
                    return;
                }

                if (sessionId > 0)
                {
                    targetSession.BindPlatformSession(sessionId, runIndex, platformName);
                    OnPlatformSessionCreated?.Invoke(sessionId);
                    Debug.Log($"[XRTestManager] Platform session created: {sessionId}, run #{runIndex}.");
                }
                else if (!string.IsNullOrEmpty(error))
                {
                    Debug.LogError($"[XRTestManager] Platform session create failed: {error}");
                }

                if (pendingUploadAfterPlatformSession && samples.Count > 0)
                {
                    pendingUploadAfterPlatformSession = false;
                    UploadData("", null);
                }
            });
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
            var renderQualityCollector = new RenderQualityCollector();

            allCollectors.Add(frameRateCollector);
            allCollectors.Add(frameTimeCollector);
            allCollectors.Add(cpuCollector);
            allCollectors.Add(gpuCollector);
            allCollectors.Add(memoryCollector);
            allCollectors.Add(deviceCollector);
            allCollectors.Add(renderQualityCollector);

            batchCollectors.Add(cpuCollector);
            batchCollectors.Add(gpuCollector);
            batchCollectors.Add(memoryCollector);
            batchCollectors.Add(deviceCollector);
            batchCollectors.Add(renderQualityCollector);
        }

        private void Reset()
        {
            EnsureRuntimeState();
        }

        private void OnValidate()
        {
            EnsureRuntimeState();
        }

        private void EnsureRuntimeState()
        {
            if (config == null)
            {
                config = new XRTestConfig();
            }

            if (allCollectors == null)
            {
                allCollectors = new List<IPerformanceCollector>();
            }

            if (batchCollectors == null)
            {
                batchCollectors = new List<IPerformanceCollector>();
            }

            if (samples == null)
            {
                samples = new List<PerformanceSample>();
            }
        }

        private void StartFrameRatePhase()
        {
            currentPhase = CollectionPhase.FrameRate;
            frameRateCollector?.StartCollecting();
            frameTimeCollector?.StartCollecting();
        }

        private void SwitchToMetricsPhase()
        {
            frameRateCollector?.StopCollecting();
            frameTimeCollector?.StopCollecting();

            foreach (var collector in batchCollectors)
            {
                collector.StartCollecting();
            }

            currentPhase = CollectionPhase.Metrics;
            collectTimer = 0f;
            lastBatchFrameCount = Time.frameCount;
            lastBatchRealTime = Time.unscaledTime;

            Debug.Log("[XRTestManager] Phase 2 started: collecting non-frame-rate metrics for 30s.");
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
            sample.frameRate = cachedFrameRate;
            sample.frameTimeMs = cachedFrameTimeMs;
            sample.rawFrameTimeMs = cachedFrameTimeMs;

            samples.Add(sample);
            OnSampleCollected?.Invoke(sample);
        }

        private void CollectMetricsSample()
        {
            var sample = CreateBaseSample(MetricsPhaseName);

            foreach (var collector in batchCollectors)
            {
                collector.Collect(ref sample);
            }

            samples.Add(sample);
            OnSampleCollected?.Invoke(sample);
        }

        #endregion
    }
}

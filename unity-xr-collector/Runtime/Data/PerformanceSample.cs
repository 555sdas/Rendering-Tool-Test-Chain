using System;

namespace XRDataCollector.Data
{
    /// <summary>
    /// 性能数据样本
    /// 包含单次采集的所有性能指标
    /// </summary>
    [Serializable]
    public class PerformanceSample
    {
        #region Session Info

        /// <summary>
        /// 样本时间戳（UTC）
        /// </summary>
        public DateTime timestamp;

        /// <summary>
        /// 所属会话 ID
        /// </summary>
        public string sessionId;

        /// <summary>
        /// 会话已运行时长
        /// </summary>
        public TimeSpan elapsedTime;

        /// <summary>
        /// 采集阶段：frame_rate 表示帧率阶段，metrics 表示其它指标阶段
        /// </summary>
        public string collectionPhase;

        #endregion

        #region Frame Metrics

        /// <summary>
        /// 当前帧率（FPS）
        /// </summary>
        public float frameRate;

        /// <summary>
        /// 平滑后的帧时间（毫秒）
        /// </summary>
        public float frameTimeMs;

        /// <summary>
        /// 原始帧时间（毫秒）
        /// </summary>
        public float rawFrameTimeMs;

        #endregion

        #region CPU Metrics

        /// <summary>
        /// CPU 使用率估算值（0-100）
        /// </summary>
        public float cpuUsagePercent;

        #endregion

        #region GPU Metrics

        /// <summary>
        /// GPU 使用率估算值（0-100）
        /// </summary>
        public float gpuUsagePercent;

        /// <summary>
        /// Draw Call 数量
        /// </summary>
        public int drawCalls;

        /// <summary>
        /// 三角形数量
        /// </summary>
        public int triangles;

        /// <summary>
        /// 顶点数量
        /// </summary>
        public int vertices;

        #endregion

        #region Memory Metrics

        /// <summary>
        /// 总分配内存（MB）
        /// </summary>
        public float totalMemoryMB;

        /// <summary>
        /// 托管堆内存（MB）
        /// </summary>
        public float managedMemoryMB;

        /// <summary>
        /// 显存使用（MB）
        /// </summary>
        public float graphicsMemoryMB;

        /// <summary>
        /// 系统预留内存（MB）
        /// </summary>
        public float systemMemoryMB;

        /// <summary>
        /// 纹理资源内存估算（MB）
        /// </summary>
        public float textureMemoryMB;

        /// <summary>
        /// RenderTexture 资源内存估算（MB）
        /// </summary>
        public float renderTextureMemoryMB;

        #endregion

        #region Render Quality Metrics

        /// <summary>
        /// 场景活动光源数量
        /// </summary>
        public int activeLightCount;

        /// <summary>
        /// 实时光源数量
        /// </summary>
        public int realtimeLightCount;

        /// <summary>
        /// 阴影投射渲染器数量
        /// </summary>
        public int shadowCasterCount;

        /// <summary>
        /// 反射探针数量
        /// </summary>
        public int reflectionProbeCount;

        /// <summary>
        /// 材质槽总数
        /// </summary>
        public int materialCount;

        /// <summary>
        /// 去重材质数量
        /// </summary>
        public int uniqueMaterialCount;

        /// <summary>
        /// 透明材质数量
        /// </summary>
        public int transparentMaterialCount;

        /// <summary>
        /// 后处理 Volume 数量
        /// </summary>
        public int postProcessVolumeCount;

        /// <summary>
        /// RenderTexture 资源数量
        /// </summary>
        public int renderTextureCount;

        /// <summary>
        /// 刚体数量
        /// </summary>
        public int rigidbodyCount;

        /// <summary>
        /// 碰撞体数量
        /// </summary>
        public int colliderCount;

        #endregion

        #region Device Info

        /// <summary>
        /// 设备信息
        /// </summary>
        public DeviceInfo deviceInfo;

        /// <summary>
        /// XR 是否处于活动状态
        /// </summary>
        public bool isXrActive;

        /// <summary>
        /// XR 设备名称
        /// </summary>
        public string xrDeviceName;

        #endregion

        #region Methods

        /// <summary>
        /// 获取样本的摘要信息
        /// </summary>
        /// <returns>摘要字符串</returns>
        public string GetSummary()
        {
            return $"时间：{timestamp:HH:mm:ss.fff}, " +
                   $"帧率：{frameRate:F1}, " +
                   $"帧时间：{frameTimeMs:F2}毫秒, " +
                   $"CPU：{cpuUsagePercent:F1}%, " +
                   $"GPU：{gpuUsagePercent:F1}%, " +
                   $"内存：{totalMemoryMB:F1}MB, " +
                   $"DrawCalls：{drawCalls}";
        }

        #endregion
    }
}

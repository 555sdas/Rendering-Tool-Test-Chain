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
            return $"Time: {timestamp:HH:mm:ss.fff}, " +
                   $"FPS: {frameRate:F1}, " +
                   $"FrameTime: {frameTimeMs:F2}ms, " +
                   $"CPU: {cpuUsagePercent:F1}%, " +
                   $"GPU: {gpuUsagePercent:F1}%, " +
                   $"Memory: {totalMemoryMB:F1}MB, " +
                   $"DrawCalls: {drawCalls}";
        }

        #endregion
    }
}

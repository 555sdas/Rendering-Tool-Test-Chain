using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// CPU 使用率采集器
    /// 采集当前 CPU 使用率估算值
    /// </summary>
    public class CpuUsageCollector : IPerformanceCollector
    {
        #region Fields

        private float cpuUsagePercent;
        private float lastFrameTime;
        private float targetFrameTime;

        #endregion

        #region IPerformanceCollector Implementation

        /// <summary>
        /// 采集器名称
        /// </summary>
        public string CollectorName => "CpuUsage";

        /// <summary>
        /// 开始采集，初始化目标帧时间
        /// </summary>
        public void StartCollecting()
        {
            cpuUsagePercent = 0f;
            lastFrameTime = 0f;
            targetFrameTime = 1000f / Application.targetFrameRate;

            if (targetFrameTime <= 0f || Application.targetFrameRate <= 0)
            {
                targetFrameTime = 16.67f;
            }
        }

        /// <summary>
        /// 停止采集
        /// </summary>
        public void StopCollecting()
        {
        }

        /// <summary>
        /// 采集 CPU 使用率估算值
        /// 基于帧时间与目标帧时间的比值进行估算
        /// </summary>
        /// <param name="sample">性能样本</param>
        public void Collect(ref PerformanceSample sample)
        {
            float currentFrameTime = Time.unscaledDeltaTime * 1000f;

            if (targetFrameTime > 0f)
            {
                float ratio = currentFrameTime / targetFrameTime;
                cpuUsagePercent = Mathf.Clamp(ratio * 100f, 0f, 100f);
            }
            else
            {
                cpuUsagePercent = 0f;
            }

            lastFrameTime = currentFrameTime;
            sample.cpuUsagePercent = cpuUsagePercent;
        }

        #endregion
    }
}

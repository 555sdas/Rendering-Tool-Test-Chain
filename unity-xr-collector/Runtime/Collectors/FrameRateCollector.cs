using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 帧率采集器
    /// 采集当前应用的每秒帧数（FPS）
    /// </summary>
    public class FrameRateCollector : IPerformanceCollector
    {
        #region Fields

        private float fpsAccumulator;
        private int fpsFrameCount;
        private float currentFps;
        private const float FpsUpdateInterval = 0.5f;
        private float fpsTimer;

        #endregion

        #region IPerformanceCollector Implementation

        /// <summary>
        /// 采集器名称
        /// </summary>
        public string CollectorName => "FrameRate";

        /// <summary>
        /// 开始采集，重置计数器
        /// </summary>
        public void StartCollecting()
        {
            fpsAccumulator = 0f;
            fpsFrameCount = 0;
            currentFps = 0f;
            fpsTimer = 0f;
        }

        /// <summary>
        /// 停止采集
        /// </summary>
        public void StopCollecting()
        {
        }

        /// <summary>
        /// 采集当前帧率数据
        /// 使用滑动窗口平均算法计算 FPS
        /// </summary>
        /// <param name="sample">性能样本</param>
        public void Collect(ref PerformanceSample sample)
        {
            UpdateFps();
            sample.frameRate = currentFps;
        }

        #endregion

        #region Private Methods

        private void UpdateFps()
        {
            fpsAccumulator += Time.unscaledDeltaTime;
            fpsFrameCount++;
            fpsTimer += Time.unscaledDeltaTime;

            if (fpsTimer >= FpsUpdateInterval)
            {
                if (fpsAccumulator > 0f)
                {
                    currentFps = fpsFrameCount / fpsAccumulator;
                }

                fpsAccumulator = 0f;
                fpsFrameCount = 0;
                fpsTimer = 0f;
            }

            if (currentFps <= 0f && Time.unscaledDeltaTime > 0f)
            {
                currentFps = 1f / Time.unscaledDeltaTime;
            }
        }

        #endregion
    }
}

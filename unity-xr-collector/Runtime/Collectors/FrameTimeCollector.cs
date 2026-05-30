using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 帧时间采集器
    /// 采集当前帧的渲染时间（毫秒）
    /// </summary>
    public class FrameTimeCollector : IPerformanceCollector
    {
        #region Fields

        private float frameTimeMs;
        private float smoothedFrameTimeMs;
        private const float SmoothingFactor = 0.1f;

        #endregion

        #region IPerformanceCollector Implementation

        /// <summary>
        /// 采集器名称
        /// </summary>
        public string CollectorName => "FrameTime";

        /// <summary>
        /// 开始采集
        /// </summary>
        public void StartCollecting()
        {
            frameTimeMs = 0f;
            smoothedFrameTimeMs = 0f;
        }

        /// <summary>
        /// 停止采集
        /// </summary>
        public void StopCollecting()
        {
        }

        /// <summary>
        /// 采集当前帧时间
        /// 将 unscaledDeltaTime 转换为毫秒，并进行平滑处理
        /// </summary>
        /// <param name="sample">性能样本</param>
        public void Collect(ref PerformanceSample sample)
        {
            frameTimeMs = Time.unscaledDeltaTime * 1000f;

            if (smoothedFrameTimeMs <= 0f)
            {
                smoothedFrameTimeMs = frameTimeMs;
            }
            else
            {
                smoothedFrameTimeMs = Mathf.Lerp(smoothedFrameTimeMs, frameTimeMs, SmoothingFactor);
            }

            sample.frameTimeMs = smoothedFrameTimeMs;
            sample.rawFrameTimeMs = frameTimeMs;
        }

        #endregion
    }
}

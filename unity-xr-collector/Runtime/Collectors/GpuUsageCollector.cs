using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    public class GpuUsageCollector : IPerformanceCollector
    {
        private float gpuUsagePercent;

        public string CollectorName => "GpuUsage";

        public void StartCollecting()
        {
            gpuUsagePercent = 0f;
            FrameTimingHelper.EnsureEnabled();
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            float totalMs = Mathf.Max(Time.unscaledDeltaTime * 1000f, 0.001f);
            if (FrameTimingHelper.TryGetLatestCpuGpuMs(out _, out float gpuMs))
                gpuUsagePercent = Mathf.Clamp01(gpuMs / totalMs) * 100f;

            sample.gpuUsagePercent = gpuUsagePercent;
        }
    }
}

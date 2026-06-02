using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    public class GpuUsageCollector : IPerformanceCollector
    {
        private float gpuUsagePercent;
        private FrameTiming[] frameTimings = new FrameTiming[1];

        public string CollectorName => "GpuUsage";

        public void StartCollecting()
        {
            gpuUsagePercent = 0f;
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            FrameTimingManager.CaptureFrameTimings();
            uint count = FrameTimingManager.GetLatestTimings(1, frameTimings);

            if (count > 0 && (float)frameTimings[0].gpuFrameTime > 0f)
            {
                float gpuMs = (float)frameTimings[0].gpuFrameTime;
                float totalMs = Time.unscaledDeltaTime * 1000f;
                gpuUsagePercent = Mathf.Clamp01(gpuMs / totalMs) * 100f;
            }
            else
            {
                gpuUsagePercent = 0f;
            }

            sample.gpuUsagePercent = gpuUsagePercent;
            sample.drawCalls = 0;
            sample.triangles = 0;
            sample.vertices = 0;
        }
    }
}

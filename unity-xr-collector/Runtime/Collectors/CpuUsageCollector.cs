using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    public class CpuUsageCollector : IPerformanceCollector
    {
        private float cpuUsagePercent;
        private FrameTiming[] frameTimings = new FrameTiming[1];

        public string CollectorName => "CpuUsage";

        public void StartCollecting()
        {
            cpuUsagePercent = 0f;
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            FrameTimingManager.CaptureFrameTimings();
            uint count = FrameTimingManager.GetLatestTimings(1, frameTimings);

            if (count > 0 && (float)frameTimings[0].cpuFrameTime > 0f)
            {
                float cpuMs = (float)frameTimings[0].cpuFrameTime;
                float totalMs = Time.unscaledDeltaTime * 1000f;
                cpuUsagePercent = Mathf.Clamp01(cpuMs / totalMs) * 100f;
            }
            else
            {
                cpuUsagePercent = 0f;
            }

            sample.cpuUsagePercent = cpuUsagePercent;
        }
    }
}

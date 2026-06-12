using System;
using System.Diagnostics;
using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    public class CpuUsageCollector : IPerformanceCollector
    {
        private float cpuUsagePercent;
        private TimeSpan previousProcessCpuTime;
        private float previousRealtime;

        public string CollectorName => "CpuUsage";

        public void StartCollecting()
        {
            cpuUsagePercent = 0f;
            previousProcessCpuTime = ReadProcessCpuTime();
            previousRealtime = Time.realtimeSinceStartup;
            FrameTimingHelper.EnsureEnabled();
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            float totalMs = Mathf.Max(Time.unscaledDeltaTime * 1000f, 0.001f);
            if (FrameTimingHelper.TryGetLatestCpuGpuMs(out float cpuMs, out _))
                cpuUsagePercent = Mathf.Clamp01(cpuMs / totalMs) * 100f;
            else
                cpuUsagePercent = ReadProcessCpuPercent();

            sample.cpuUsagePercent = cpuUsagePercent;
        }

        private float ReadProcessCpuPercent()
        {
            TimeSpan currentCpuTime = ReadProcessCpuTime();
            float currentRealtime = Time.realtimeSinceStartup;
            double cpuSeconds = (currentCpuTime - previousProcessCpuTime).TotalSeconds;
            float wallSeconds = currentRealtime - previousRealtime;
            previousProcessCpuTime = currentCpuTime;
            previousRealtime = currentRealtime;
            if (wallSeconds <= 0f || cpuSeconds < 0d)
                return cpuUsagePercent;
            return Mathf.Clamp((float)(cpuSeconds / wallSeconds / Math.Max(1, SystemInfo.processorCount) * 100d), 0f, 100f);
        }

        private static TimeSpan ReadProcessCpuTime()
        {
            using (var process = Process.GetCurrentProcess())
                return process.TotalProcessorTime;
        }
    }
}

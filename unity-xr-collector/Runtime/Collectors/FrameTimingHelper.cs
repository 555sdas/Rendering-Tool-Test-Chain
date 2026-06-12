using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace XRDataCollector.Collectors
{
    internal static class FrameTimingHelper
    {
        private static bool featurePrepared;

        public static void EnsureEnabled()
        {
            if (featurePrepared)
                return;

#if UNITY_EDITOR
            try
            {
                var playerSettingsType = System.Type.GetType("UnityEditor.PlayerSettings, UnityEditor");
                var property = playerSettingsType?.GetProperty("enableFrameTimingStats");
                if (property != null && property.PropertyType == typeof(bool))
                    property.SetValue(null, true);
            }
            catch
            {
                // Editor-only reflection fallback; runtime builds rely on project settings.
            }
#endif

            featurePrepared = true;
        }

        internal static void ResetDomainState()
        {
            featurePrepared = false;
        }

        public static bool TryGetLatestCpuGpuMs(out float cpuMs, out float gpuMs)
        {
            cpuMs = 0f;
            gpuMs = 0f;

            EnsureEnabled();
            FrameTimingManager.CaptureFrameTimings();

            var timings = new FrameTiming[4];
            uint count = FrameTimingManager.GetLatestTimings((uint)timings.Length, timings);
            if (count == 0)
                return false;

            for (int i = 0; i < count; i++)
            {
                float sampleCpu = (float)timings[i].cpuFrameTime;
                float sampleGpu = (float)timings[i].gpuFrameTime;
                if (sampleCpu > cpuMs) cpuMs = sampleCpu;
                if (sampleGpu > gpuMs) gpuMs = sampleGpu;
            }

#if UNITY_EDITOR
            if (gpuMs <= 0f && UnityStats.renderTime > 0f)
                gpuMs = UnityStats.renderTime;
#endif
            return cpuMs > 0f || gpuMs > 0f;
        }
    }
}

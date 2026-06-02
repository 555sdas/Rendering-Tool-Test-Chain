using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    public class FrameRateCollector : IPerformanceCollector
    {
        private float currentFps;
        private int lastFrameCount;
        private float lastCollectRealTime;

        public string CollectorName => "FrameRate";

        public void StartCollecting()
        {
            currentFps = 0f;
            lastFrameCount = Time.frameCount;
            lastCollectRealTime = Time.unscaledTime;
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            int currentFrameCount = Time.frameCount;
            float currentTime = Time.unscaledTime;

            int framesPassed = currentFrameCount - lastFrameCount;
            float timePassed = currentTime - lastCollectRealTime;

            if (framesPassed > 0 && timePassed > 0f)
            {
                currentFps = framesPassed / timePassed;
            }
            else if (Time.unscaledDeltaTime > 0f)
            {
                currentFps = 1f / Time.unscaledDeltaTime;
            }

            lastFrameCount = currentFrameCount;
            lastCollectRealTime = currentTime;

            sample.frameRate = currentFps;
        }
    }
}

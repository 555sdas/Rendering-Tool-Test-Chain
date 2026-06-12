using System.Collections.Generic;
using UnityEngine;
using XRDataCollector.Core;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 对已加载 Texture / RenderTexture 求运行时内存估算。
    /// </summary>
    public class ResourceMemoryCollector : IPerformanceCollector
    {
        private readonly XRTestConfig config;
        private int collectCounter;
        private float cachedTextureMemoryMB;
        private float cachedRenderTextureMemoryMB;

        public string CollectorName => "ResourceMemory";

        public ResourceMemoryCollector(XRTestConfig config = null)
        {
            this.config = config;
        }

        public void StartCollecting()
        {
            collectCounter = 0;
            cachedTextureMemoryMB = 0f;
            cachedRenderTextureMemoryMB = 0f;
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            collectCounter++;
            if (collectCounter == 1 || collectCounter % 10 == 0)
                RefreshCachedMemory();

            if (IsTextureMemoryEnabled())
                sample.textureMemoryMB = cachedTextureMemoryMB;
            if (IsRenderTextureMemoryEnabled())
                sample.renderTextureMemoryMB = cachedRenderTextureMemoryMB;
        }

        public float GetTextureMemoryMB() => cachedTextureMemoryMB;
        public float GetRenderTextureMemoryMB() => cachedRenderTextureMemoryMB;

        private bool IsTextureMemoryEnabled()
        {
            return config == null || config.testMaterialTextureMemory;
        }

        private bool IsRenderTextureMemoryEnabled()
        {
            return config == null || config.testPostProcessRenderTextureMemory;
        }

        private void RefreshCachedMemory()
        {
            long textureBytes = 0;
            long renderTextureBytes = 0;

            var textures = Resources.FindObjectsOfTypeAll<Texture>();
            foreach (var texture in textures)
            {
                if (texture == null) continue;
                long size = UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(texture);
                if (texture is RenderTexture)
                    renderTextureBytes += size;
                else
                    textureBytes += size;
            }

            cachedTextureMemoryMB = BytesToMB(textureBytes);
            cachedRenderTextureMemoryMB = BytesToMB(renderTextureBytes);
        }

        private static float BytesToMB(long bytes)
        {
            return bytes / (1024f * 1024f);
        }
    }
}

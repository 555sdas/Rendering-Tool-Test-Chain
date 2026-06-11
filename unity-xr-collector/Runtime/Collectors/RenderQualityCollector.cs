using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.Rendering;
using XRDataCollector.Core;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 渲染质量相关场景指标采集器
    /// 采集光照、材质、后处理和物理仿真规模指标，用于后端做规则化预测试评分。
    /// </summary>
    public class RenderQualityCollector : IPerformanceCollector
    {
        private int activeLightCount;
        private int realtimeLightCount;
        private int shadowCasterCount;
        private int reflectionProbeCount;
        private int materialCount;
        private int uniqueMaterialCount;
        private int transparentMaterialCount;
        private int postProcessVolumeCount;
        private int renderTextureCount;
        private float textureMemoryMB;
        private float renderTextureMemoryMB;
        private int rigidbodyCount;
        private int colliderCount;
        private readonly XRTestConfig config;

        public string CollectorName => "RenderQuality";

        public RenderQualityCollector(XRTestConfig config = null)
        {
            this.config = config;
        }

        public void StartCollecting()
        {
            ResetMetrics();
            if (config == null || config.testLightingQuality)
                CollectLightingMetrics();
            if (config == null || config.testMaterialQuality)
                CollectMaterialMetrics();
            if (config == null || config.testPostProcessingQuality)
                CollectPostProcessingMetrics();
            if (config == null || config.testPhysicsQuality)
                CollectPhysicsMetrics();

            Debug.Log(
                "[RenderQualityCollector] 渲染质量采集完成：" +
                $"光照={(IsLightingEnabled() ? $"光源{activeLightCount}/阴影{shadowCasterCount}/反射探针{reflectionProbeCount}" : "未勾选")}；" +
                $"材质={(IsMaterialEnabled() ? $"材质{materialCount}/唯一材质{uniqueMaterialCount}/透明{transparentMaterialCount}" : "未勾选")}；" +
                $"后处理={(IsPostProcessingEnabled() ? $"Volume{postProcessVolumeCount}/RenderTexture{renderTextureCount}" : "未勾选")}；" +
                $"物理={(IsPhysicsEnabled() ? $"刚体{rigidbodyCount}/碰撞体{colliderCount}" : "未勾选")}"
            );
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            sample.activeLightCount = activeLightCount;
            sample.realtimeLightCount = realtimeLightCount;
            sample.shadowCasterCount = shadowCasterCount;
            sample.reflectionProbeCount = reflectionProbeCount;
            sample.materialCount = materialCount;
            sample.uniqueMaterialCount = uniqueMaterialCount;
            sample.transparentMaterialCount = transparentMaterialCount;
            sample.postProcessVolumeCount = postProcessVolumeCount;
            sample.renderTextureCount = renderTextureCount;
            sample.textureMemoryMB = textureMemoryMB;
            sample.renderTextureMemoryMB = renderTextureMemoryMB;
            sample.rigidbodyCount = rigidbodyCount;
            sample.colliderCount = colliderCount;
        }

        private void ResetMetrics()
        {
            activeLightCount = IsLightingMetricEnabled(config?.testLightingActiveLights ?? true) ? 0 : -1;
            realtimeLightCount = IsLightingMetricEnabled(config?.testLightingRealtimeLights ?? true) ? 0 : -1;
            shadowCasterCount = IsLightingMetricEnabled(config?.testLightingShadowCasters ?? true) ? 0 : -1;
            reflectionProbeCount = IsLightingMetricEnabled(config?.testLightingReflectionProbes ?? true) ? 0 : -1;
            materialCount = IsMaterialMetricEnabled(config?.testMaterialSlots ?? true) ? 0 : -1;
            uniqueMaterialCount = IsMaterialMetricEnabled(config?.testMaterialUniqueMaterials ?? true) ? 0 : -1;
            transparentMaterialCount = IsMaterialMetricEnabled(config?.testMaterialTransparentMaterials ?? true) ? 0 : -1;
            postProcessVolumeCount = IsPostProcessingMetricEnabled(config?.testPostProcessVolumes ?? true) ? 0 : -1;
            renderTextureCount = IsPostProcessingMetricEnabled(config?.testPostProcessRenderTextures ?? true) ? 0 : -1;
            textureMemoryMB = IsMaterialMetricEnabled(config?.testMaterialTextureMemory ?? true) ? 0f : -1f;
            renderTextureMemoryMB = IsPostProcessingMetricEnabled(config?.testPostProcessRenderTextureMemory ?? true) ? 0f : -1f;
            rigidbodyCount = IsPhysicsMetricEnabled(config?.testPhysicsRigidbodies ?? true) ? 0 : -1;
            colliderCount = IsPhysicsMetricEnabled(config?.testPhysicsColliders ?? true) ? 0 : -1;
        }

        private bool IsLightingEnabled()
        {
            return config == null || config.testLightingQuality;
        }

        private bool IsMaterialEnabled()
        {
            return config == null || config.testMaterialQuality;
        }

        private bool IsPostProcessingEnabled()
        {
            return config == null || config.testPostProcessingQuality;
        }

        private bool IsPhysicsEnabled()
        {
            return config == null || config.testPhysicsQuality;
        }

        private bool IsLightingMetricEnabled(bool metricEnabled)
        {
            return IsLightingEnabled() && metricEnabled;
        }

        private bool IsMaterialMetricEnabled(bool metricEnabled)
        {
            return IsMaterialEnabled() && metricEnabled;
        }

        private bool IsPostProcessingMetricEnabled(bool metricEnabled)
        {
            return IsPostProcessingEnabled() && metricEnabled;
        }

        private bool IsPhysicsMetricEnabled(bool metricEnabled)
        {
            return IsPhysicsEnabled() && metricEnabled;
        }

        private void CollectLightingMetrics()
        {
            if (IsLightingMetricEnabled(config?.testLightingActiveLights ?? true) ||
                IsLightingMetricEnabled(config?.testLightingRealtimeLights ?? true))
            {
                var lights = UnityEngine.Object.FindObjectsOfType<Light>();
                if (IsLightingMetricEnabled(config?.testLightingActiveLights ?? true))
                    activeLightCount = 0;
                if (IsLightingMetricEnabled(config?.testLightingRealtimeLights ?? true))
                    realtimeLightCount = 0;

                foreach (var light in lights)
                {
                    if (light == null || !light.isActiveAndEnabled) continue;

                    if (IsLightingMetricEnabled(config?.testLightingActiveLights ?? true))
                        activeLightCount++;
                    if (IsLightingMetricEnabled(config?.testLightingRealtimeLights ?? true) &&
                        light.lightmapBakeType == LightmapBakeType.Realtime)
                    {
                        realtimeLightCount++;
                    }
                }
            }

            if (IsLightingMetricEnabled(config?.testLightingShadowCasters ?? true))
            {
                shadowCasterCount = 0;
                var renderers = UnityEngine.Object.FindObjectsOfType<Renderer>();
                foreach (var renderer in renderers)
                {
                    if (renderer == null || !renderer.enabled) continue;
                    if (renderer.shadowCastingMode != ShadowCastingMode.Off)
                    {
                        shadowCasterCount++;
                    }
                }
            }

            if (IsLightingMetricEnabled(config?.testLightingReflectionProbes ?? true))
                reflectionProbeCount = UnityEngine.Object.FindObjectsOfType<ReflectionProbe>().Length;
        }

        private void CollectMaterialMetrics()
        {
            bool collectSlots = IsMaterialMetricEnabled(config?.testMaterialSlots ?? true);
            bool collectUnique = IsMaterialMetricEnabled(config?.testMaterialUniqueMaterials ?? true);
            bool collectTransparent = IsMaterialMetricEnabled(config?.testMaterialTransparentMaterials ?? true);
            bool collectTextureMemory = IsMaterialMetricEnabled(config?.testMaterialTextureMemory ?? true);
            if (!collectSlots && !collectUnique && !collectTransparent && !collectTextureMemory) return;

            if (collectSlots) materialCount = 0;
            if (collectTransparent) transparentMaterialCount = 0;
            var uniqueMaterials = new HashSet<int>();
            var renderers = UnityEngine.Object.FindObjectsOfType<Renderer>();

            foreach (var renderer in renderers)
            {
                if (renderer == null || !renderer.enabled) continue;

                foreach (var material in renderer.sharedMaterials)
                {
                    if (material == null) continue;

                    if (collectSlots) materialCount++;
                    if (collectUnique) uniqueMaterials.Add(material.GetInstanceID());

                    if (collectTransparent && (material.renderQueue >= 3000 || IsTransparentShader(material)))
                    {
                        transparentMaterialCount++;
                    }
                }
            }

            if (collectUnique) uniqueMaterialCount = uniqueMaterials.Count;

            if (collectTextureMemory)
            {
                textureMemoryMB = CalculateTextureMemoryMB(includeRenderTextures: false);
            }
        }

        private bool IsTransparentShader(Material material)
        {
            if (material.shader == null) return false;

            string shaderName = material.shader.name.ToLowerInvariant();
            return shaderName.Contains("transparent") ||
                   shaderName.Contains("glass") ||
                   shaderName.Contains("particle");
        }

        private void CollectPostProcessingMetrics()
        {
            if (IsPostProcessingMetricEnabled(config?.testPostProcessVolumes ?? true))
            {
                var volumeType = Type.GetType("UnityEngine.Rendering.Volume, Unity.RenderPipelines.Core.Runtime");
                if (volumeType != null)
                {
                    var volumes = UnityEngine.Object.FindObjectsOfType(volumeType);
                    postProcessVolumeCount = volumes.Length;
                }
                else
                {
                    postProcessVolumeCount = 0;
                }
            }
            if (IsPostProcessingMetricEnabled(config?.testPostProcessRenderTextures ?? true))
                renderTextureCount = Resources.FindObjectsOfTypeAll<RenderTexture>().Length;
            if (IsPostProcessingMetricEnabled(config?.testPostProcessRenderTextureMemory ?? true))
                renderTextureMemoryMB = CalculateRenderTextureMemoryMB();
        }

        private void CollectPhysicsMetrics()
        {
            if (IsPhysicsMetricEnabled(config?.testPhysicsRigidbodies ?? true))
                rigidbodyCount = UnityEngine.Object.FindObjectsOfType<Rigidbody>().Length;
            if (IsPhysicsMetricEnabled(config?.testPhysicsColliders ?? true))
                colliderCount = UnityEngine.Object.FindObjectsOfType<Collider>().Length;
        }

        private static float CalculateTextureMemoryMB(bool includeRenderTextures)
        {
            long totalBytes = 0;
            var textures = Resources.FindObjectsOfTypeAll<Texture>();
            foreach (var texture in textures)
            {
                if (texture == null) continue;
                if (!includeRenderTextures && texture is RenderTexture) continue;
                totalBytes += Profiler.GetRuntimeMemorySizeLong(texture);
            }
            return BytesToMB(totalBytes);
        }

        private static float CalculateRenderTextureMemoryMB()
        {
            long totalBytes = 0;
            var renderTextures = Resources.FindObjectsOfTypeAll<RenderTexture>();
            foreach (var renderTexture in renderTextures)
            {
                if (renderTexture == null) continue;
                totalBytes += Profiler.GetRuntimeMemorySizeLong(renderTexture);
            }
            return BytesToMB(totalBytes);
        }

        private static float BytesToMB(long bytes)
        {
            return bytes / (1024f * 1024f);
        }
    }
}

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
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
        private int rigidbodyCount;
        private int colliderCount;

        public string CollectorName => "RenderQuality";

        public void StartCollecting()
        {
            ResetMetrics();
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
        {
            CollectLightingMetrics();
            CollectMaterialMetrics();
            CollectPostProcessingMetrics();
            CollectPhysicsMetrics();

            sample.activeLightCount = activeLightCount;
            sample.realtimeLightCount = realtimeLightCount;
            sample.shadowCasterCount = shadowCasterCount;
            sample.reflectionProbeCount = reflectionProbeCount;
            sample.materialCount = materialCount;
            sample.uniqueMaterialCount = uniqueMaterialCount;
            sample.transparentMaterialCount = transparentMaterialCount;
            sample.postProcessVolumeCount = postProcessVolumeCount;
            sample.renderTextureCount = renderTextureCount;
            sample.rigidbodyCount = rigidbodyCount;
            sample.colliderCount = colliderCount;
        }

        private void ResetMetrics()
        {
            activeLightCount = 0;
            realtimeLightCount = 0;
            shadowCasterCount = 0;
            reflectionProbeCount = 0;
            materialCount = 0;
            uniqueMaterialCount = 0;
            transparentMaterialCount = 0;
            postProcessVolumeCount = 0;
            renderTextureCount = 0;
            rigidbodyCount = 0;
            colliderCount = 0;
        }

        private void CollectLightingMetrics()
        {
            var lights = Object.FindObjectsOfType<Light>();
            activeLightCount = 0;
            realtimeLightCount = 0;

            foreach (var light in lights)
            {
                if (light == null || !light.isActiveAndEnabled) continue;

                activeLightCount++;
                if (light.lightmapBakeType == LightmapBakeType.Realtime)
                {
                    realtimeLightCount++;
                }
            }

            shadowCasterCount = 0;
            var renderers = Object.FindObjectsOfType<Renderer>();
            foreach (var renderer in renderers)
            {
                if (renderer == null || !renderer.enabled) continue;
                if (renderer.shadowCastingMode != ShadowCastingMode.Off)
                {
                    shadowCasterCount++;
                }
            }

            reflectionProbeCount = Object.FindObjectsOfType<ReflectionProbe>().Length;
        }

        private void CollectMaterialMetrics()
        {
            materialCount = 0;
            transparentMaterialCount = 0;
            var uniqueMaterials = new HashSet<int>();
            var renderers = Object.FindObjectsOfType<Renderer>();

            foreach (var renderer in renderers)
            {
                if (renderer == null || !renderer.enabled) continue;

                foreach (var material in renderer.sharedMaterials)
                {
                    if (material == null) continue;

                    materialCount++;
                    uniqueMaterials.Add(material.GetInstanceID());

                    if (material.renderQueue >= 3000 || IsTransparentShader(material))
                    {
                        transparentMaterialCount++;
                    }
                }
            }

            uniqueMaterialCount = uniqueMaterials.Count;
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
            postProcessVolumeCount = Object.FindObjectsOfType<Volume>().Length;
            renderTextureCount = Resources.FindObjectsOfTypeAll<RenderTexture>().Length;
        }

        private void CollectPhysicsMetrics()
        {
            rigidbodyCount = Object.FindObjectsOfType<Rigidbody>().Length;
            colliderCount = Object.FindObjectsOfType<Collider>().Length;
        }
    }
}

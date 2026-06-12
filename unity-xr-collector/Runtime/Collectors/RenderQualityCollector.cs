using System;
using System.Collections.Generic;
using UnityEngine;
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
        private const int MaxPenetrationColliders = 200;

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
        private int postProcessingWarningCount;
        private int penetrationEventCount;
        private readonly XRTestConfig config;

        public string CollectorName => "RenderQuality";

        public RenderQualityCollector(XRTestConfig config = null)
        {
            this.config = config;
        }

        public void StartCollecting()
        {
            ResetMetrics();
        }

        public void StopCollecting()
        {
        }

        public void Collect(ref PerformanceSample sample)
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
            sample.postProcessingWarningCount = postProcessingWarningCount;
            sample.penetrationEventCount = penetrationEventCount;
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
            rigidbodyCount = IsPhysicsMetricEnabled(config?.testPhysicsRigidbodies ?? true) ? 0 : -1;
            colliderCount = IsPhysicsMetricEnabled(config?.testPhysicsColliders ?? true) ? 0 : -1;
            postProcessingWarningCount = IsPostProcessingMetricEnabled(config?.testPostProcessWarnings ?? true) ? 0 : -1;
            penetrationEventCount = IsPhysicsMetricEnabled(config?.testPhysicsPenetration ?? true) ? 0 : -1;
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
            var lights = UnityEngine.Object.FindObjectsOfType<Light>();
            bool collectActiveLights = IsLightingMetricEnabled(config?.testLightingActiveLights ?? true);
            bool collectRealtimeLights = IsLightingMetricEnabled(config?.testLightingRealtimeLights ?? true);

            foreach (var light in lights)
            {
                if (light == null || !light.isActiveAndEnabled) continue;

                if (collectActiveLights) activeLightCount++;
                if (collectRealtimeLights && light.lightmapBakeType == LightmapBakeType.Realtime)
                {
                    realtimeLightCount++;
                }
            }

            if (IsLightingMetricEnabled(config?.testLightingShadowCasters ?? true))
            {
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
            materialCount = 0;
            transparentMaterialCount = 0;
            var uniqueMaterials = new HashSet<int>();
            var renderers = UnityEngine.Object.FindObjectsOfType<Renderer>();

            foreach (var renderer in renderers)
            {
                if (renderer == null || !renderer.enabled) continue;

                foreach (var material in renderer.sharedMaterials)
                {
                    if (material == null) continue;

                    if (IsMaterialMetricEnabled(config?.testMaterialSlots ?? true))
                        materialCount++;
                    if (IsMaterialMetricEnabled(config?.testMaterialUniqueMaterials ?? true))
                        uniqueMaterials.Add(material.GetInstanceID());

                    if (IsMaterialMetricEnabled(config?.testMaterialTransparentMaterials ?? true) &&
                        (material.renderQueue >= 3000 || IsTransparentShader(material)))
                    {
                        transparentMaterialCount++;
                    }
                }
            }

            if (IsMaterialMetricEnabled(config?.testMaterialUniqueMaterials ?? true))
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
            if (IsPostProcessingMetricEnabled(config?.testPostProcessVolumes ?? true))
            {
                var volumeType = Type.GetType("UnityEngine.Rendering.Volume, Unity.RenderPipelines.Core.Runtime");
                postProcessVolumeCount = volumeType != null
                    ? UnityEngine.Object.FindObjectsOfType(volumeType).Length
                    : 0;
            }
            if (IsPostProcessingMetricEnabled(config?.testPostProcessRenderTextures ?? true))
                renderTextureCount = Resources.FindObjectsOfTypeAll<RenderTexture>().Length;
            if (IsPostProcessingMetricEnabled(config?.testPostProcessWarnings ?? true))
                postProcessingWarningCount = AuditPostProcessingConfiguration();
        }

        private void CollectPhysicsMetrics()
        {
            if (IsPhysicsMetricEnabled(config?.testPhysicsRigidbodies ?? true))
                rigidbodyCount = UnityEngine.Object.FindObjectsOfType<Rigidbody>().Length;
            if (IsPhysicsMetricEnabled(config?.testPhysicsColliders ?? true))
                colliderCount = UnityEngine.Object.FindObjectsOfType<Collider>().Length;
            if (IsPhysicsMetricEnabled(config?.testPhysicsPenetration ?? true))
                penetrationEventCount = CountPenetratingColliderPairs();
        }

        private int AuditPostProcessingConfiguration()
        {
            var volumeType = Type.GetType("UnityEngine.Rendering.Volume, Unity.RenderPipelines.Core.Runtime");
            if (volumeType == null) return 0;

            int warningCount = 0;
            var sharedProfileProperty = volumeType.GetProperty("sharedProfile");
            foreach (var volume in UnityEngine.Object.FindObjectsOfType(volumeType))
            {
                if (!(volume is Behaviour behaviour) || !behaviour.isActiveAndEnabled) continue;
                var profile = sharedProfileProperty?.GetValue(volume, null);
                if (profile == null) warningCount++;
            }
            return warningCount;
        }

        private int CountPenetratingColliderPairs()
        {
            var allColliders = UnityEngine.Object.FindObjectsOfType<Collider>();
            var colliders = new List<Collider>(Mathf.Min(allColliders.Length, MaxPenetrationColliders));
            foreach (var collider in allColliders)
            {
                if (colliders.Count >= MaxPenetrationColliders) break;
                if (collider == null || !collider.enabled || collider.isTrigger || !collider.gameObject.activeInHierarchy)
                    continue;
                colliders.Add(collider);
            }

            int penetrationCount = 0;
            for (int i = 0; i < colliders.Count; i++)
            {
                var first = colliders[i];
                for (int j = i + 1; j < colliders.Count; j++)
                {
                    var second = colliders[j];
                    if (first.attachedRigidbody != null && first.attachedRigidbody == second.attachedRigidbody)
                        continue;
                    if (!first.bounds.Intersects(second.bounds))
                        continue;

                    if (Physics.ComputePenetration(
                        first, first.transform.position, first.transform.rotation,
                        second, second.transform.position, second.transform.rotation,
                        out _, out float distance) && distance > 0.001f)
                    {
                        penetrationCount++;
                    }
                }
            }
            return penetrationCount;
        }
    }
}

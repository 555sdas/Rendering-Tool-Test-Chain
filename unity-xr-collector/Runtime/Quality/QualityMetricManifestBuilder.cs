using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using XRDataCollector.Core;
using XRDataCollector.Data;

namespace XRDataCollector.Quality
{
    public static class QualityMetricManifestBuilder
    {
        public static List<Dictionary<string, object>> Build(
            XRTestConfig config,
            IReadOnlyList<PerformanceSample> samples)
        {
            var manifest = new List<Dictionary<string, object>>();
            if (config == null) return manifest;

            AddSceneCountMetric(manifest, "lighting.active_lights", config.testLightingActiveLights, CountValid(samples, s => s.activeLightCount));
            AddSceneCountMetric(manifest, "lighting.realtime_lights", config.testLightingRealtimeLights, CountValid(samples, s => s.realtimeLightCount));
            AddSceneCountMetric(manifest, "lighting.shadow_casters", config.testLightingShadowCasters, CountValid(samples, s => s.shadowCasterCount));
            AddSceneCountMetric(manifest, "lighting.reflection_probes", config.testLightingReflectionProbes, CountValid(samples, s => s.reflectionProbeCount));
            AddUnavailable(manifest, "lighting.exposure_artifacts", config.testLightingExposureArtifacts, "not_implemented", "conditional");

            AddSceneCountMetric(manifest, "materials.material_slots", config.testMaterialSlots, CountValid(samples, s => s.materialCount));
            AddSceneCountMetric(manifest, "materials.unique_materials", config.testMaterialUniqueMaterials, CountValid(samples, s => s.uniqueMaterialCount));
            AddSceneCountMetric(manifest, "materials.transparent_materials", config.testMaterialTransparentMaterials, CountValid(samples, s => s.transparentMaterialCount));
            AddSceneCountMetric(manifest, "materials.draw_calls", config.testMaterialDrawCalls, CountValid(samples, s => s.drawCalls));
            AddMemoryMetric(manifest, "materials.texture_memory", config.testMaterialTextureMemory, CountValidFloat(samples, s => s.textureMemoryMB), "MB");

            AddVolumeMetric(config, samples, manifest);
            AddSceneCountMetric(manifest, "post_processing.render_textures", config.testPostProcessRenderTextures, CountValid(samples, s => s.renderTextureCount));
            AddMemoryMetric(manifest, "post_processing.render_texture_memory", config.testPostProcessRenderTextureMemory, CountValidFloat(samples, s => s.renderTextureMemoryMB), "MB");
            AddDerivedGpuBudget(config, samples, manifest);
            AddConditionalCountMetric(manifest, "post_processing.warnings", config.testPostProcessWarnings, CountValid(samples, s => s.postProcessingWarningCount));

            AddSceneCountMetric(manifest, "physics.rigidbodies", config.testPhysicsRigidbodies, CountValid(samples, s => s.rigidbodyCount));
            AddSceneCountMetric(manifest, "physics.colliders", config.testPhysicsColliders, CountValid(samples, s => s.colliderCount));
            AddConditionalCountMetric(manifest, "physics.penetration", config.testPhysicsPenetration, CountValid(samples, s => s.penetrationEventCount));
            AddUnavailable(manifest, "physics.pose_latency", config.testPhysicsPoseLatency, "provider_not_installed", "provider_required");
            AddUnavailable(manifest, "physics.prediction_error", config.testPhysicsPredictionError, "provider_not_installed", "provider_required");
            AddLongFramesMetric(config, samples, manifest);

            foreach (var entry in manifest)
            {
                Debug.Log($"[QualityMetrics] {entry["id"]}: {entry["status"]}, reason={entry["reasonCode"]}");
            }

            return manifest;
        }

        private static void AddVolumeMetric(XRTestConfig config, IReadOnlyList<PerformanceSample> samples, List<Dictionary<string, object>> manifest)
        {
            if (!config.testPostProcessVolumes)
            {
                AddSkipped(manifest, "post_processing.volumes");
                return;
            }

            var volumeType = Type.GetType("UnityEngine.Rendering.Volume, Unity.RenderPipelines.Core.Runtime");
            if (volumeType == null)
            {
                manifest.Add(Entry("post_processing.volumes", "unavailable", "unsupported_render_pipeline", "conditional", 0));
                return;
            }

            AddSceneCountMetric(manifest, "post_processing.volumes", true, CountValid(samples, s => s.postProcessVolumeCount));
        }

        private static void AddDerivedGpuBudget(XRTestConfig config, IReadOnlyList<PerformanceSample> samples, List<Dictionary<string, object>> manifest)
        {
            if (!config.testPostProcessGpuFrameBudget)
            {
                AddSkipped(manifest, "post_processing.gpu_frame_budget");
                return;
            }

            int gpuCount = CountValidFloat(samples, s => s.gpuUsagePercent);
            int frameCount = CountValidFloat(samples, s => s.frameTimeMs);
            if (gpuCount > 0 && frameCount > 0)
                manifest.Add(Entry("post_processing.gpu_frame_budget", "available", null, "derived", gpuCount));
            else
                manifest.Add(Entry("post_processing.gpu_frame_budget", "unavailable", "derived_dependency_missing", "derived", 0));
        }

        private static void AddLongFramesMetric(XRTestConfig config, IReadOnlyList<PerformanceSample> samples, List<Dictionary<string, object>> manifest)
        {
            if (!config.testPhysicsLongFrames)
            {
                AddSkipped(manifest, "physics.long_frames");
                return;
            }

            manifest.Add(Entry("physics.long_frames", "available", null, "derived", samples.Count));
        }

        private static void AddSceneCountMetric(
            List<Dictionary<string, object>> manifest,
            string id,
            bool enabled,
            int validSampleCount)
        {
            if (!enabled)
            {
                AddSkipped(manifest, id);
                return;
            }

            if (validSampleCount > 0)
                manifest.Add(Entry(id, "available", null, "native", validSampleCount));
            else
                manifest.Add(Entry(id, "missing", "no_valid_samples", "native", 0));
        }

        private static void AddMemoryMetric(
            List<Dictionary<string, object>> manifest,
            string id,
            bool enabled,
            int validSampleCount,
            string unit)
        {
            if (!enabled)
            {
                AddSkipped(manifest, id);
                return;
            }

            if (validSampleCount > 0)
            {
                var entry = Entry(id, "available", null, "native", validSampleCount);
                entry["unit"] = unit;
                entry["provider"] = "UnityResourceMemoryProvider";
                manifest.Add(entry);
            }
            else
                manifest.Add(Entry(id, "missing", "no_valid_samples", "native", 0));
        }

        private static void AddConditionalCountMetric(
            List<Dictionary<string, object>> manifest,
            string id,
            bool enabled,
            int validSampleCount)
        {
            if (!enabled)
            {
                AddSkipped(manifest, id);
                return;
            }

            if (validSampleCount > 0)
                manifest.Add(Entry(id, "available", null, "conditional", validSampleCount));
            else
                manifest.Add(Entry(id, "missing", "no_valid_samples", "conditional", 0));
        }

        private static void AddUnavailable(
            List<Dictionary<string, object>> manifest,
            string id,
            bool enabled,
            string reasonCode,
            string tier)
        {
            if (!enabled)
            {
                AddSkipped(manifest, id);
                return;
            }

            manifest.Add(Entry(id, "unavailable", reasonCode, tier, 0));
        }

        private static void AddSkipped(List<Dictionary<string, object>> manifest, string id)
        {
            manifest.Add(Entry(id, "skipped", "not_selected", "native", 0));
        }

        private static Dictionary<string, object> Entry(
            string id,
            string status,
            string reasonCode,
            string tier,
            int validSampleCount)
        {
            return new Dictionary<string, object>
            {
                ["id"] = id,
                ["status"] = status,
                ["reasonCode"] = reasonCode,
                ["measurementTier"] = tier,
                ["validSampleCount"] = validSampleCount,
                ["errorCount"] = 0,
            };
        }

        private static int CountValid(IReadOnlyList<PerformanceSample> samples, Func<PerformanceSample, int> selector)
        {
            int count = 0;
            foreach (var sample in samples)
            {
                int value = selector(sample);
                if (value >= 0) count++;
            }
            return count;
        }

        private static int CountValidFloat(IReadOnlyList<PerformanceSample> samples, Func<PerformanceSample, float> selector)
        {
            int count = 0;
            foreach (var sample in samples)
            {
                float value = selector(sample);
                if (value >= 0f) count++;
            }
            return count;
        }

        public static string SerializeManifest(List<Dictionary<string, object>> manifest)
        {
            var sb = new StringBuilder();
            sb.Append("[");
            for (int i = 0; i < manifest.Count; i++)
            {
                var entry = manifest[i];
                sb.Append("{");
                sb.Append($"\"id\": \"{entry["id"]}\",");
                sb.Append($"\"status\": \"{entry["status"]}\",");
                sb.Append($"\"reasonCode\": {(entry["reasonCode"] == null ? "null" : $"\"{entry["reasonCode"]}\"")},");
                sb.Append($"\"measurementTier\": \"{entry["measurementTier"]}\",");
                sb.Append($"\"validSampleCount\": {entry["validSampleCount"]},");
                sb.Append($"\"errorCount\": {entry["errorCount"]}");
                if (entry.ContainsKey("provider"))
                    sb.Append($",\"provider\": \"{entry["provider"]}\"");
                if (entry.ContainsKey("unit"))
                    sb.Append($",\"unit\": \"{entry["unit"]}\"");
                sb.Append("}");
                if (i < manifest.Count - 1) sb.Append(",");
            }
            sb.Append("]");
            return sb.ToString();
        }
    }
}

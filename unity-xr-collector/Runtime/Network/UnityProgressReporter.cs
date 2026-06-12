using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using XRDataCollector.Core;

namespace XRDataCollector.Network
{
    public class UnityProgressReporter : MonoBehaviour
    {
        private XRTestManager manager;
        private float nextReportTime;
        private bool requestInFlight;

        public void Initialize(XRTestManager testManager)
        {
            manager = testManager;
            nextReportTime = 0f;
        }

        private void OnDisable()
        {
            StopAllCoroutines();
            requestInFlight = false;
        }

        private void Update()
        {
            if (manager == null || manager.Config == null || string.IsNullOrEmpty(manager.Config.progressUrl))
                return;
            if (Time.unscaledTime < nextReportTime)
                return;
            if (requestInFlight)
                return;
            nextReportTime = Time.unscaledTime + 1f;
            StartCoroutine(SendProgress());
        }

        private IEnumerator SendProgress()
        {
            requestInFlight = true;
            var sample = manager.BuildLiveProgressSample();
            var payload = new ProgressPayload
            {
                task_id = manager.Config.testTaskId,
                session_id = manager.Config.platformSessionId,
                phase = manager.IsCollecting ? (sample?.collectionPhase ?? "starting") : "uploading",
                phase_label = manager.IsCollecting ? manager.CurrentCollectionPhase : "上传结果",
                progress = manager.IsCollecting ? manager.CollectionProgress : 1f,
                remaining_seconds = manager.CurrentPhaseRemainingSeconds,
                sample_count = manager.GetSampleCount(),
                fps = sample?.frameRate ?? 0f,
                frame_time_ms = sample?.frameTimeMs ?? 0f,
                raw_frame_time_ms = sample?.rawFrameTimeMs ?? 0f,
                cpu_usage_percent = sample?.cpuUsagePercent ?? 0f,
                gpu_usage_percent = sample?.gpuUsagePercent ?? 0f,
                memory_mb = sample?.totalMemoryMB ?? 0f,
                managed_memory_mb = sample?.managedMemoryMB ?? 0f,
                graphics_memory_mb = sample?.graphicsMemoryMB ?? 0f,
                system_memory_mb = sample?.systemMemoryMB ?? 0f,
                draw_calls = sample?.drawCalls ?? 0,
                triangles = sample?.triangles ?? 0,
                vertices = sample?.vertices ?? 0,
                active_light_count = sample?.activeLightCount ?? 0,
                realtime_light_count = sample?.realtimeLightCount ?? 0,
                shadow_caster_count = sample?.shadowCasterCount ?? 0,
                reflection_probe_count = sample?.reflectionProbeCount ?? 0,
                material_count = sample?.materialCount ?? 0,
                unique_material_count = sample?.uniqueMaterialCount ?? 0,
                transparent_material_count = sample?.transparentMaterialCount ?? 0,
                post_process_volume_count = sample?.postProcessVolumeCount ?? 0,
                render_texture_count = sample?.renderTextureCount ?? 0,
                rigidbody_count = sample?.rigidbodyCount ?? 0,
                collider_count = sample?.colliderCount ?? 0,
                is_xr_active = sample?.isXrActive ?? false,
                xr_device_name = sample?.xrDeviceName ?? "",
                device_model = sample?.deviceInfo?.deviceModel ?? "",
                operating_system = sample?.deviceInfo?.operatingSystem ?? "",
                unity_version = sample?.deviceInfo?.unityVersion ?? Application.unityVersion,
                graphics_device_name = sample?.deviceInfo?.graphicsDeviceName ?? "",
                render_pipeline = sample?.deviceInfo?.renderPipeline ?? "",
                screen_resolution = sample?.deviceInfo?.screenResolution ?? ""
            };
            byte[] body = Encoding.UTF8.GetBytes(JsonUtility.ToJson(payload));
            using (var request = new UnityWebRequest(manager.Config.progressUrl, "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(body);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.SetRequestHeader("X-Device-Token", manager.Config.deviceToken);
                request.timeout = 5;
                yield return request.SendWebRequest();
#if UNITY_2020_1_OR_NEWER
                if (request.result != UnityWebRequest.Result.Success)
#else
                if (request.isNetworkError || request.isHttpError)
#endif
                    Debug.LogWarning($"[UnityProgressReporter] 实时数据上报失败：HTTP {request.responseCode} {request.error}，URL={manager.Config.progressUrl}");
            }
            requestInFlight = false;
        }

        [Serializable]
        private class ProgressPayload
        {
            public int task_id;
            public int session_id;
            public string phase;
            public string phase_label;
            public float progress;
            public float remaining_seconds;
            public int sample_count;
            public float fps;
            public float frame_time_ms;
            public float raw_frame_time_ms;
            public float cpu_usage_percent;
            public float gpu_usage_percent;
            public float memory_mb;
            public float managed_memory_mb;
            public float graphics_memory_mb;
            public float system_memory_mb;
            public int draw_calls;
            public int triangles;
            public int vertices;
            public int active_light_count;
            public int realtime_light_count;
            public int shadow_caster_count;
            public int reflection_probe_count;
            public int material_count;
            public int unique_material_count;
            public int transparent_material_count;
            public int post_process_volume_count;
            public int render_texture_count;
            public int rigidbody_count;
            public int collider_count;
            public bool is_xr_active;
            public string xr_device_name;
            public string device_model;
            public string operating_system;
            public string unity_version;
            public string graphics_device_name;
            public string render_pipeline;
            public string screen_resolution;
        }
    }
}

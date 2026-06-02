using System;
using System.Collections;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using XRDataCollector.Core;
using XRDataCollector.Data;

namespace XRDataCollector.Network
{
    /// <summary>
    /// 测试数据上传器
    /// 通过 HTTP POST 将测试数据上传到服务器
    /// </summary>
    public class TestDataUploader
    {
        #region Fields

        private MonoBehaviour coroutineHost;

        #endregion

        #region Public Methods

        /// <summary>
        /// 异步上传测试数据
        /// </summary>
        /// <param name="samples">性能样本列表</param>
        /// <param name="session">测试会话信息</param>
        /// <param name="url">上传目标地址</param>
        /// <param name="callback">上传完成回调，参数为是否成功</param>
        public void UploadAsync(List<PerformanceSample> samples, XRTestSession session, string url, string authToken, Action<bool> callback)
        {
            if (samples == null || samples.Count == 0)
            {
                Debug.LogWarning("[TestDataUploader] No samples to upload.");
                callback?.Invoke(false);
                return;
            }

            if (string.IsNullOrEmpty(url))
            {
                Debug.LogError("[TestDataUploader] Upload URL is empty.");
                callback?.Invoke(false);
                return;
            }

            var host = GetCoroutineHost();
            if (host == null)
            {
                Debug.LogError("[TestDataUploader] Cannot find a MonoBehaviour to run coroutine.");
                callback?.Invoke(false);
                return;
            }

            string jsonPayload = BuildJsonPayload(samples, session);
            host.StartCoroutine(UploadCoroutine(url, jsonPayload, authToken, callback));
        }

        public void UploadAsync(List<PerformanceSample> samples, XRTestSession session, XRTestConfig config, Action<bool> callback)
        {
            if (samples == null || samples.Count == 0)
            {
                Debug.LogWarning("[TestDataUploader] No samples to upload.");
                callback?.Invoke(false);
                return;
            }

            if (config == null)
            {
                Debug.LogError("[TestDataUploader] XRTestConfig is null.");
                callback?.Invoke(false);
                return;
            }

            var host = GetCoroutineHost();
            if (host == null)
            {
                Debug.LogError("[TestDataUploader] Cannot find a MonoBehaviour to run coroutine.");
                callback?.Invoke(false);
                return;
            }

            host.StartCoroutine(AutoSyncCoroutine(samples, session, config, callback));
        }

        #endregion

        #region Private Methods

        private MonoBehaviour GetCoroutineHost()
        {
            if (coroutineHost != null) return coroutineHost;

            if (XRTestManager.Instance != null)
            {
                coroutineHost = XRTestManager.Instance;
                return coroutineHost;
            }

            var go = new GameObject("XRTestUploaderHost");
            coroutineHost = go.AddComponent<UploaderHost>();
            return coroutineHost;
        }

        private IEnumerator UploadCoroutine(string url, string jsonPayload, string authToken, Action<bool> callback)
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

            using (var request = new UnityWebRequest(url, "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                if (!string.IsNullOrEmpty(authToken))
                {
                    request.SetRequestHeader("Authorization", "Bearer " + authToken);
                }
                request.timeout = 30;

                yield return request.SendWebRequest();

                bool success = false;

#if UNITY_2020_1_OR_NEWER
                if (request.result == UnityWebRequest.Result.Success)
#else
                if (!request.isNetworkError && !request.isHttpError)
#endif
                {
                    Debug.Log($"[TestDataUploader] Upload successful. Response: {request.downloadHandler.text}");
                    success = true;
                }
                else
                {
                    Debug.LogError($"[TestDataUploader] Upload failed: {request.error}");
                    success = false;
                }

                callback?.Invoke(success);
            }
        }

        private IEnumerator AutoSyncCoroutine(List<PerformanceSample> samples, XRTestSession session, XRTestConfig config, Action<bool> callback)
        {
            string baseUrl = NormalizeBaseUrl(config.platformBaseUrl);
            if (string.IsNullOrEmpty(baseUrl))
            {
                Debug.LogError("[TestDataUploader] Platform base URL is empty.");
                callback?.Invoke(false);
                yield break;
            }

            string token = config.authToken;
            if (string.IsNullOrEmpty(token))
            {
                yield return LoginCoroutine(baseUrl, config.username, config.password, value => token = value);
            }

            if (string.IsNullOrEmpty(token))
            {
                Debug.LogError("[TestDataUploader] Cannot upload without token.");
                callback?.Invoke(false);
                yield break;
            }

            string uploadUrl = config.uploadUrl;
            if (string.IsNullOrEmpty(uploadUrl) || config.autoCreateSession)
            {
                int sessionId = 0;
                yield return CreateSessionCoroutine(baseUrl, token, config, session, samples[0], value => sessionId = value);
                if (sessionId <= 0)
                {
                    callback?.Invoke(false);
                    yield break;
                }
                uploadUrl = $"{baseUrl}/data-collection/test-sessions/{sessionId}/samples/batch";
            }

            string jsonPayload = BuildJsonPayload(samples, session);
            bool uploadSuccess = false;
            yield return UploadCoroutine(uploadUrl, jsonPayload, token, success => uploadSuccess = success);
            callback?.Invoke(uploadSuccess);
        }

        private IEnumerator LoginCoroutine(string baseUrl, string username, string password, Action<string> callback)
        {
            using (var request = new UnityWebRequest($"{baseUrl}/auth/login", "POST"))
            {
                string form = $"username={UnityWebRequest.EscapeURL(username)}&password={UnityWebRequest.EscapeURL(password)}";
                byte[] bodyRaw = Encoding.UTF8.GetBytes(form);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/x-www-form-urlencoded");
                request.timeout = 30;

                yield return request.SendWebRequest();

#if UNITY_2020_1_OR_NEWER
                bool success = request.result == UnityWebRequest.Result.Success;
#else
                bool success = !request.isNetworkError && !request.isHttpError;
#endif
                if (!success)
                {
                    Debug.LogError($"[TestDataUploader] Login failed: {request.error} {request.downloadHandler.text}");
                    callback?.Invoke(null);
                    yield break;
                }

                callback?.Invoke(ExtractStringField(request.downloadHandler.text, "access_token"));
            }
        }

        private IEnumerator CreateSessionCoroutine(
            string baseUrl,
            string token,
            XRTestConfig config,
            XRTestSession session,
            PerformanceSample firstSample,
            Action<int> callback)
        {
            string body = BuildCreateSessionJson(config, session, firstSample);
            byte[] bodyRaw = Encoding.UTF8.GetBytes(body);

            using (var request = new UnityWebRequest($"{baseUrl}/data-collection/test-sessions", "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json; charset=utf-8");
                request.SetRequestHeader("Authorization", "Bearer " + token);
                request.timeout = 30;

                yield return request.SendWebRequest();

#if UNITY_2020_1_OR_NEWER
                bool success = request.result == UnityWebRequest.Result.Success;
#else
                bool success = !request.isNetworkError && !request.isHttpError;
#endif
                if (!success)
                {
                    Debug.LogError($"[TestDataUploader] Create session failed: {request.error} {request.downloadHandler.text}");
                    callback?.Invoke(0);
                    yield break;
                }

                callback?.Invoke(ExtractIntField(request.downloadHandler.text, "id"));
            }
        }

        private string BuildJsonPayload(List<PerformanceSample> samples, XRTestSession session)
        {
            var sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine("  \"uploadTime\": \"" + DateTime.UtcNow.ToString("O") + "\",");

            if (session != null)
            {
                sb.AppendLine("  \"session\": {");
                sb.AppendLine($"    \"sessionId\": \"{session.SessionId}\",");
                sb.AppendLine($"    \"sessionName\": \"{EscapeJson(session.SessionName)}\",");
                sb.AppendLine($"    \"startTime\": \"{session.StartTime:O}\",");
                sb.AppendLine($"    \"duration\": {session.ElapsedTime.TotalSeconds:F3},");
                sb.AppendLine($"    \"unityVersion\": \"{EscapeJson(session.UnityVersion)}\",");
                sb.AppendLine($"    \"productName\": \"{EscapeJson(session.ProductName)}\",");
                sb.AppendLine($"    \"appVersion\": \"{EscapeJson(session.AppVersion)}\"");
                sb.AppendLine("  },");
            }

            sb.AppendLine("  \"sampleCount\": " + samples.Count + ",");
            sb.AppendLine("  \"samples\": [");

            for (int i = 0; i < samples.Count; i++)
            {
                var s = samples[i];
                sb.AppendLine("    {");
                sb.AppendLine($"      \"timestamp\": \"{s.timestamp:O}\",");
                sb.AppendLine($"      \"elapsedTime\": {s.elapsedTime.TotalSeconds:F3},");
                sb.AppendLine($"      \"collectionPhase\": \"{EscapeJson(s.collectionPhase)}\",");

                if (s.collectionPhase == "frame_rate")
                {
                    sb.AppendLine($"      \"frameRate\": {s.frameRate:F2},");
                    sb.AppendLine($"      \"frameTimeMs\": {s.frameTimeMs:F3},");
                    sb.AppendLine("      \"extraMetrics\": {");
                    sb.AppendLine("        \"collection_phase\": \"frame_rate\"");
                    sb.AppendLine("      }");
                }
                else
                {
                    sb.AppendLine($"      \"cpuUsagePercent\": {s.cpuUsagePercent:F2},");
                    sb.AppendLine($"      \"gpuUsagePercent\": {s.gpuUsagePercent:F2},");
                    sb.AppendLine($"      \"drawCalls\": {s.drawCalls},");
                    sb.AppendLine($"      \"totalMemoryMB\": {s.totalMemoryMB:F2},");
                    sb.AppendLine($"      \"managedMemoryMB\": {s.managedMemoryMB:F2},");
                    sb.AppendLine($"      \"graphicsMemoryMB\": {s.graphicsMemoryMB:F2},");
                    AppendDeviceInfo(sb, s.deviceInfo);
                    sb.AppendLine("      \"renderQuality\": {");
                    sb.AppendLine($"        \"active_light_count\": {s.activeLightCount},");
                    sb.AppendLine($"        \"realtime_light_count\": {s.realtimeLightCount},");
                    sb.AppendLine($"        \"shadow_caster_count\": {s.shadowCasterCount},");
                    sb.AppendLine($"        \"reflection_probe_count\": {s.reflectionProbeCount},");
                    sb.AppendLine($"        \"material_count\": {s.materialCount},");
                    sb.AppendLine($"        \"unique_material_count\": {s.uniqueMaterialCount},");
                    sb.AppendLine($"        \"transparent_material_count\": {s.transparentMaterialCount},");
                    sb.AppendLine($"        \"post_process_volume_count\": {s.postProcessVolumeCount},");
                    sb.AppendLine($"        \"render_texture_count\": {s.renderTextureCount},");
                    sb.AppendLine($"        \"rigidbody_count\": {s.rigidbodyCount},");
                    sb.AppendLine($"        \"collider_count\": {s.colliderCount}");
                    sb.AppendLine("      },");
                    sb.AppendLine("      \"extraMetrics\": {");
                    sb.AppendLine("        \"collection_phase\": \"metrics\"");
                    sb.AppendLine("      }");
                }

                sb.Append("    }");
                sb.AppendLine(i < samples.Count - 1 ? "," : "");
            }

            sb.AppendLine("  ]");
            sb.AppendLine("}");

            return sb.ToString();
        }

        private void AppendDeviceInfo(StringBuilder sb, DeviceInfo info)
        {
            if (info == null)
            {
                sb.AppendLine("      \"deviceInfo\": null,");
                return;
            }

            sb.AppendLine("      \"deviceInfo\": {");
            sb.AppendLine($"        \"deviceModel\": \"{EscapeJson(info.deviceModel)}\",");
            sb.AppendLine($"        \"deviceName\": \"{EscapeJson(info.deviceName)}\",");
            sb.AppendLine($"        \"operatingSystem\": \"{EscapeJson(info.operatingSystem)}\",");
            sb.AppendLine($"        \"processorType\": \"{EscapeJson(info.processorType)}\",");
            sb.AppendLine($"        \"processorCount\": {info.processorCount},");
            sb.AppendLine($"        \"systemMemorySize\": {info.systemMemorySize},");
            sb.AppendLine($"        \"graphicsDeviceName\": \"{EscapeJson(info.graphicsDeviceName)}\",");
            sb.AppendLine($"        \"graphicsDeviceVendor\": \"{EscapeJson(info.graphicsDeviceVendor)}\",");
            sb.AppendLine($"        \"graphicsDeviceVersion\": \"{EscapeJson(info.graphicsDeviceVersion)}\",");
            sb.AppendLine($"        \"graphicsMemorySize\": {info.graphicsMemorySize},");
            sb.AppendLine($"        \"screenResolution\": \"{EscapeJson(info.screenResolution)}\"");
            sb.AppendLine("      },");
        }

        private string BuildCreateSessionJson(XRTestConfig config, XRTestSession session, PerformanceSample sample)
        {
            var info = sample.deviceInfo;
            string name = string.IsNullOrEmpty(config.sessionName)
                ? $"Unity采集-{DateTime.Now:yyyyMMdd-HHmmss}"
                : config.sessionName;
            string deviceModel = info != null ? info.deviceModel : SystemInfo.deviceModel;
            string osVersion = info != null ? info.operatingSystem : SystemInfo.operatingSystem;
            string appVersion = session != null ? session.AppVersion : Application.version;
            string unityVersion = session != null ? session.UnityVersion : Application.unityVersion;

            var sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine($"  \"name\": \"{EscapeJson(name)}\",");
            sb.AppendLine("  \"description\": \"Unity插件自动同步创建\",");
            sb.AppendLine($"  \"device_model\": \"{EscapeJson(deviceModel)}\",");
            sb.AppendLine($"  \"os_version\": \"{EscapeJson(osVersion)}\",");
            sb.AppendLine("  \"xr_runtime\": \"Unity Editor / OpenXR\",");
            sb.AppendLine($"  \"app_version\": \"{EscapeJson(appVersion)}\",");
            sb.AppendLine($"  \"scene_id\": {config.sceneId},");
            sb.AppendLine($"  \"project_id\": {config.projectId},");
            sb.AppendLine("  \"config\": {");
            sb.AppendLine($"    \"unity_version\": \"{EscapeJson(unityVersion)}\",");
            sb.AppendLine($"    \"gpu_model\": \"{EscapeJson(info != null ? info.graphicsDeviceName : SystemInfo.graphicsDeviceName)}\",");
            sb.AppendLine($"    \"gpu_vendor\": \"{EscapeJson(info != null ? info.graphicsDeviceVendor : SystemInfo.graphicsDeviceVendor)}\",");
            sb.AppendLine($"    \"gpu_version\": \"{EscapeJson(info != null ? info.graphicsDeviceVersion : SystemInfo.graphicsDeviceVersion)}\",");
            sb.AppendLine($"    \"system_memory_mb\": {(info != null ? info.systemMemorySize : SystemInfo.systemMemorySize)},");
            sb.AppendLine($"    \"gpu_memory_mb\": {(info != null ? info.graphicsMemorySize : SystemInfo.graphicsMemorySize)},");
            sb.AppendLine($"    \"screen_resolution\": \"{Screen.width}x{Screen.height}\",");
            sb.AppendLine("    \"sync_mode\": \"unity_auto_sync\"");
            sb.AppendLine("  }");
            sb.AppendLine("}");
            return sb.ToString();
        }

        private string NormalizeBaseUrl(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            return value.Trim().TrimEnd('/');
        }

        private string ExtractStringField(string json, string field)
        {
            var match = Regex.Match(json, $"\"{field}\"\\s*:\\s*\"([^\"]+)\"");
            return match.Success ? match.Groups[1].Value : null;
        }

        private int ExtractIntField(string json, string field)
        {
            var match = Regex.Match(json, $"\"{field}\"\\s*:\\s*(\\d+)");
            if (match.Success && int.TryParse(match.Groups[1].Value, out int value))
            {
                return value;
            }
            return 0;
        }

        private string EscapeJson(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\n", "\\n")
                .Replace("\r", "\\r")
                .Replace("\t", "\\t");
        }

        #endregion

        #region Nested Class

        /// <summary>
        /// 用于运行协程的内部 MonoBehaviour
        /// </summary>
        private class UploaderHost : MonoBehaviour
        {
            private void Awake()
            {
                DontDestroyOnLoad(gameObject);
                hideFlags = HideFlags.HideAndDontSave;
            }
        }

        #endregion
    }
}

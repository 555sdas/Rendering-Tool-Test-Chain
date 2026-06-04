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
        public void UploadAsync(List<PerformanceSample> samples, XRTestSession session, string url, string authToken, Action<bool> callback)
        {
            if (samples == null || samples.Count == 0)
            {
                Debug.LogWarning("[TestDataUploader] 没有可上传的样本。");
                callback?.Invoke(false);
                return;
            }

            if (string.IsNullOrEmpty(url))
            {
                Debug.LogError("[TestDataUploader] 上传地址为空。");
                callback?.Invoke(false);
                return;
            }

            var host = GetCoroutineHost();
            if (host == null)
            {
                Debug.LogError("[TestDataUploader] 找不到 MonoBehaviour 来运行协程。");
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
                Debug.LogWarning("[TestDataUploader] 没有可上传的样本。");
                callback?.Invoke(false);
                return;
            }

            if (config == null)
            {
                Debug.LogError("[TestDataUploader] XRTestConfig 为空。");
                callback?.Invoke(false);
                return;
            }

            var host = GetCoroutineHost();
            if (host == null)
            {
                Debug.LogError("[TestDataUploader] 找不到 MonoBehaviour 来运行协程。");
                callback?.Invoke(false);
                return;
            }

            host.StartCoroutine(AutoSyncCoroutine(samples, session, config, callback));
        }

        public void LoadProjectsAsync(XRTestConfig config, Action<List<PlatformProject>, string> callback)
        {
            if (config == null)
            {
                callback?.Invoke(null, "XRTestConfig 为空。");
                return;
            }

            var host = GetCoroutineHost();
            if (host == null)
            {
                callback?.Invoke(null, "找不到 MonoBehaviour 来运行协程。");
                return;
            }

            host.StartCoroutine(LoadProjectsCoroutine(config, callback));
        }

        public void CreatePlatformSessionAsync(XRTestConfig config, XRTestSession session, Action<int, int, string, string> callback)
        {
            if (config == null)
            {
                callback?.Invoke(0, 0, null, "XRTestConfig 为空。");
                return;
            }

            if (session == null)
            {
                callback?.Invoke(0, 0, null, "XRTestSession 为空。");
                return;
            }

            var host = GetCoroutineHost();
            if (host == null)
            {
                callback?.Invoke(0, 0, null, "找不到 MonoBehaviour 来运行协程。");
                return;
            }

            host.StartCoroutine(CreatePlatformSessionFlowCoroutine(config, session, callback));
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
                    request.SetRequestHeader("Authorization", "Bearer " + authToken);
                request.timeout = 30;

                yield return request.SendWebRequest();

                bool success = false;
#if UNITY_2020_1_OR_NEWER
                if (request.result == UnityWebRequest.Result.Success)
#else
                if (!request.isNetworkError && !request.isHttpError)
#endif
                {
                    Debug.Log($"[TestDataUploader] 上传成功。响应：{request.downloadHandler.text}");
                    success = true;
                }
                else
                {
                    Debug.LogError($"[TestDataUploader] 上传失败：{request.error}");
                    success = false;
                }
                callback?.Invoke(success);
            }
        }

        private IEnumerator LoadProjectsCoroutine(XRTestConfig config, Action<List<PlatformProject>, string> callback)
        {
            string baseUrl = NormalizeBaseUrl(config.platformBaseUrl);
            if (string.IsNullOrEmpty(baseUrl))
            {
                callback?.Invoke(null, "平台 API 地址为空。");
                yield break;
            }

            string token = null;
            yield return EnsureAuthTokenCoroutine(config, baseUrl, value => token = value);
            if (string.IsNullOrEmpty(token))
            {
                callback?.Invoke(null, "登录失败，请检查用户名、密码或令牌。");
                yield break;
            }

            using (var request = UnityWebRequest.Get($"{baseUrl}/data-collection/platform/projects?limit=100"))
            {
                request.downloadHandler = new DownloadHandlerBuffer();
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
                    callback?.Invoke(null, $"加载项目列表失败：{request.error} {request.downloadHandler.text}");
                    yield break;
                }

                var projects = ParseProjectList(request.downloadHandler.text);
                callback?.Invoke(projects, null);
            }
        }

        private IEnumerator CreatePlatformSessionFlowCoroutine(
            XRTestConfig config, XRTestSession session,
            Action<int, int, string, string> callback)
        {
            string baseUrl = NormalizeBaseUrl(config.platformBaseUrl);
            if (string.IsNullOrEmpty(baseUrl))
            {
                callback?.Invoke(0, 0, null, "平台 API 地址为空。");
                yield break;
            }

            string token = null;
            yield return EnsureAuthTokenCoroutine(config, baseUrl, value => token = value);
            if (string.IsNullOrEmpty(token))
            {
                callback?.Invoke(0, 0, null, "登录失败，请检查用户名、密码或令牌。");
                yield break;
            }

            yield return CreatePlatformSessionCoroutine(baseUrl, token, config, session, callback);
        }

        private IEnumerator AutoSyncCoroutine(List<PerformanceSample> samples, XRTestSession session, XRTestConfig config, Action<bool> callback)
        {
            string baseUrl = NormalizeBaseUrl(config.platformBaseUrl);
            if (string.IsNullOrEmpty(baseUrl))
            {
                Debug.LogError("[TestDataUploader] 平台 API 地址为空。");
                callback?.Invoke(false);
                yield break;
            }

            string token = null;
            yield return EnsureAuthTokenCoroutine(config, baseUrl, value => token = value);
            if (string.IsNullOrEmpty(token))
            {
                Debug.LogError("[TestDataUploader] 无法上传：缺少令牌。");
                callback?.Invoke(false);
                yield break;
            }

            string uploadUrl = config.uploadUrl;
            if (config.autoCreateSession)
            {
                int sessionId = session != null ? session.PlatformSessionId : 0;
                if (sessionId <= 0)
                {
                    int runIndex = 0;
                    string platformName = null;
                    string error = null;
                    yield return CreatePlatformSessionCoroutine(baseUrl, token, config, session,
                        (id, index, name, message) =>
                        {
                            sessionId = id;
                            runIndex = index;
                            platformName = name;
                            error = message;
                        });

                    if (sessionId > 0 && session != null)
                        session.BindPlatformSession(sessionId, runIndex, platformName);

                    if (!string.IsNullOrEmpty(error))
                        Debug.LogError($"[TestDataUploader] 创建平台会话失败：{error}");
                }

                if (sessionId <= 0)
                {
                    callback?.Invoke(false);
                    yield break;
                }
                uploadUrl = $"{baseUrl}/data-collection/test-sessions/{sessionId}/samples/batch";
            }
            else if (string.IsNullOrEmpty(uploadUrl))
            {
                Debug.LogError("[TestDataUploader] 上传地址为空且未启用自动创建会话。");
                callback?.Invoke(false);
                yield break;
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
                    Debug.LogError($"[TestDataUploader] 登录失败：{request.error} {request.downloadHandler.text}");
                    callback?.Invoke(null);
                    yield break;
                }
                callback?.Invoke(ExtractStringField(request.downloadHandler.text, "access_token"));
            }
        }

        private IEnumerator EnsureAuthTokenCoroutine(XRTestConfig config, string baseUrl, Action<string> callback)
        {
            string token = config.authToken;
            if (string.IsNullOrEmpty(token))
            {
                yield return LoginCoroutine(baseUrl, config.username, config.password, value => token = value);
                if (!string.IsNullOrEmpty(token))
                    config.authToken = token;
            }
            callback?.Invoke(token);
        }

        private IEnumerator CreatePlatformSessionCoroutine(
            string baseUrl, string token, XRTestConfig config, XRTestSession session,
            Action<int, int, string, string> callback)
        {
            string body = BuildCreateSessionJson(config, session);
            byte[] bodyRaw = Encoding.UTF8.GetBytes(body);

            using (var request = new UnityWebRequest($"{baseUrl}/data-collection/platform/test-sessions/auto-start", "POST"))
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
                    callback?.Invoke(0, 0, null, $"{request.error} {request.downloadHandler.text}");
                    yield break;
                }

                int sessionId = ExtractIntField(request.downloadHandler.text, "id");
                int runIndex = ExtractIntField(request.downloadHandler.text, "run_index");
                string name = ExtractStringField(request.downloadHandler.text, "name");
                callback?.Invoke(sessionId, runIndex, name, null);
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

        private string BuildCreateSessionJson(XRTestConfig config, XRTestSession session)
        {
            var sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine($"  \"projectId\": {config.projectId},");
            sb.AppendLine($"  \"sceneId\": {config.sceneId},");
            sb.AppendLine($"  \"sessionName\": \"{EscapeJson(session?.SessionName ?? config.sessionName)}\",");
            sb.AppendLine($"  \"description\": \"Unity auto-created session for project {config.projectId}\"");
            sb.AppendLine("}");
            return sb.ToString();
        }

        private string EscapeJson(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            return value.Replace("\\", "\\\\").Replace("\"", "\\\"")
                        .Replace("\n", "\\n").Replace("\r", "\\r").Replace("\t", "\\t");
        }

        private string ExtractStringField(string json, string field)
        {
            var match = Regex.Match(json, $"\"{field}\"\\s*:\\s*\"([^\"]+)\"");
            return match.Success ? match.Groups[1].Value : null;
        }

        private int ExtractIntField(string json, string field)
        {
            var match = Regex.Match(json, $"\"{field}\"\\s*:\\s*(\\d+)");
            return match.Success ? int.Parse(match.Groups[1].Value) : 0;
        }

        private List<PlatformProject> ParseProjectList(string json)
        {
            if (string.IsNullOrEmpty(json))
                return new List<PlatformProject>();
            try
            {
                var response = JsonUtility.FromJson<PlatformProjectListResponse>(json);
                return response != null && response.items != null
                    ? response.items
                    : new List<PlatformProject>();
            }
            catch (Exception e)
            {
                Debug.LogError($"[TestDataUploader] 解析项目列表失败：{e.Message}");
                return new List<PlatformProject>();
            }
        }

        private string NormalizeBaseUrl(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            return value.Trim().TrimEnd('/');
        }

        #endregion
    }

    internal class UploaderHost : MonoBehaviour
    {
        private void Awake()
        {
            DontDestroyOnLoad(gameObject);
        }
    }
}

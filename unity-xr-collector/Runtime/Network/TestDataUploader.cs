using System;
using System.Collections;
using System.Collections.Generic;
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
                sb.AppendLine($"      \"frameRate\": {s.frameRate:F2},");
                sb.AppendLine($"      \"frameTimeMs\": {s.frameTimeMs:F3},");
                sb.AppendLine($"      \"cpuUsagePercent\": {s.cpuUsagePercent:F2},");
                sb.AppendLine($"      \"gpuUsagePercent\": {s.gpuUsagePercent:F2},");
                sb.AppendLine($"      \"drawCalls\": {s.drawCalls},");
                sb.AppendLine($"      \"totalMemoryMB\": {s.totalMemoryMB:F2},");
                sb.AppendLine($"      \"managedMemoryMB\": {s.managedMemoryMB:F2},");
                sb.AppendLine($"      \"graphicsMemoryMB\": {s.graphicsMemoryMB:F2},");
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
                sb.AppendLine("      }");
                sb.Append("    }");
                sb.AppendLine(i < samples.Count - 1 ? "," : "");
            }

            sb.AppendLine("  ]");
            sb.AppendLine("}");

            return sb.ToString();
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

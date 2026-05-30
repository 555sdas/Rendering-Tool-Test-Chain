using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using XRDataCollector.Core;
using XRDataCollector.Data;

namespace XRDataCollector.Exporters
{
    /// <summary>
    /// JSON 数据导出器
    /// 将性能数据导出为 JSON 格式文件
    /// </summary>
    public class JsonExporter : IDataExporter
    {
        #region IDataExporter Implementation

        /// <summary>
        /// 导出器名称
        /// </summary>
        public string ExporterName => "JSON";

        /// <summary>
        /// 导出文件扩展名
        /// </summary>
        public string FileExtension => ".json";

        /// <summary>
        /// 导出性能数据为 JSON 格式
        /// </summary>
        /// <param name="samples">性能样本列表</param>
        /// <param name="session">测试会话信息</param>
        /// <param name="filePath">目标文件路径</param>
        public void Export(List<PerformanceSample> samples, XRTestSession session, string filePath)
        {
            if (samples == null || samples.Count == 0)
            {
                throw new ArgumentException("Samples list is empty or null.", nameof(samples));
            }

            string directory = Path.GetDirectoryName(filePath);
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var json = BuildJson(samples, session);
            File.WriteAllText(filePath, json, Encoding.UTF8);
        }

        #endregion

        #region Private Methods

        private string BuildJson(List<PerformanceSample> samples, XRTestSession session)
        {
            var sb = new StringBuilder();
            sb.AppendLine("{");

            AppendSessionInfo(sb, session);
            sb.AppendLine("  \"samples\": [");

            for (int i = 0; i < samples.Count; i++)
            {
                AppendSample(sb, samples[i], i == samples.Count - 1);
            }

            sb.AppendLine("  ]");
            sb.AppendLine("}");

            return sb.ToString();
        }

        private void AppendSessionInfo(StringBuilder sb, XRTestSession session)
        {
            if (session == null)
            {
                sb.AppendLine("  \"session\": null,");
                return;
            }

            sb.AppendLine("  \"session\": {");
            sb.AppendLine($"    \"sessionId\": \"{EscapeJson(session.SessionId)}\",");
            sb.AppendLine($"    \"sessionName\": \"{EscapeJson(session.SessionName)}\",");
            sb.AppendLine($"    \"startTime\": \"{session.StartTime:O}\",");
            sb.AppendLine($"    \"endTime\": \"{session.EndTime?.ToString("O") ?? "null"}\",");
            sb.AppendLine($"    \"duration\": {session.ElapsedTime.TotalSeconds:F3},");
            sb.AppendLine($"    \"unityVersion\": \"{EscapeJson(session.UnityVersion)}\",");
            sb.AppendLine($"    \"productName\": \"{EscapeJson(session.ProductName)}\",");
            sb.AppendLine($"    \"appVersion\": \"{EscapeJson(session.AppVersion)}\",");
            sb.AppendLine($"    \"platform\": \"{EscapeJson(session.Platform)}\"");
            sb.AppendLine("  },");
        }

        private void AppendSample(StringBuilder sb, PerformanceSample sample, bool isLast)
        {
            sb.AppendLine("    {");
            sb.AppendLine($"      \"timestamp\": \"{sample.timestamp:O}\",");
            sb.AppendLine($"      \"elapsedTime\": {sample.elapsedTime.TotalSeconds:F3},");
            sb.AppendLine($"      \"frameRate\": {sample.frameRate:F2},");
            sb.AppendLine($"      \"frameTimeMs\": {sample.frameTimeMs:F3},");
            sb.AppendLine($"      \"rawFrameTimeMs\": {sample.rawFrameTimeMs:F3},");
            sb.AppendLine($"      \"cpuUsagePercent\": {sample.cpuUsagePercent:F2},");
            sb.AppendLine($"      \"gpuUsagePercent\": {sample.gpuUsagePercent:F2},");
            sb.AppendLine($"      \"drawCalls\": {sample.drawCalls},");
            sb.AppendLine($"      \"triangles\": {sample.triangles},");
            sb.AppendLine($"      \"vertices\": {sample.vertices},");
            sb.AppendLine($"      \"totalMemoryMB\": {sample.totalMemoryMB:F2},");
            sb.AppendLine($"      \"managedMemoryMB\": {sample.managedMemoryMB:F2},");
            sb.AppendLine($"      \"graphicsMemoryMB\": {sample.graphicsMemoryMB:F2},");
            sb.AppendLine($"      \"systemMemoryMB\": {sample.systemMemoryMB:F2},");
            sb.AppendLine($"      \"isXrActive\": {sample.isXrActive.ToString().ToLower()},");
            sb.AppendLine($"      \"xrDeviceName\": \"{EscapeJson(sample.xrDeviceName ?? "")}\",");
            sb.AppendLine($"      \"activeLightCount\": {sample.activeLightCount},");
            sb.AppendLine($"      \"realtimeLightCount\": {sample.realtimeLightCount},");
            sb.AppendLine($"      \"shadowCasterCount\": {sample.shadowCasterCount},");
            sb.AppendLine($"      \"reflectionProbeCount\": {sample.reflectionProbeCount},");
            sb.AppendLine($"      \"materialCount\": {sample.materialCount},");
            sb.AppendLine($"      \"uniqueMaterialCount\": {sample.uniqueMaterialCount},");
            sb.AppendLine($"      \"transparentMaterialCount\": {sample.transparentMaterialCount},");
            sb.AppendLine($"      \"postProcessVolumeCount\": {sample.postProcessVolumeCount},");
            sb.AppendLine($"      \"renderTextureCount\": {sample.renderTextureCount},");
            sb.AppendLine($"      \"rigidbodyCount\": {sample.rigidbodyCount},");
            sb.AppendLine($"      \"colliderCount\": {sample.colliderCount}");

            if (sample.deviceInfo != null)
            {
                sb.AppendLine(",");
                AppendDeviceInfo(sb, sample.deviceInfo);
            }
            else
            {
                sb.AppendLine();
            }

            sb.Append("    }");
            sb.AppendLine(isLast ? "" : ",");
        }

        private void AppendDeviceInfo(StringBuilder sb, DeviceInfo info)
        {
            sb.AppendLine("      \"deviceInfo\": {");
            sb.AppendLine($"        \"deviceModel\": \"{EscapeJson(info.deviceModel)}\",");
            sb.AppendLine($"        \"deviceName\": \"{EscapeJson(info.deviceName)}\",");
            sb.AppendLine($"        \"deviceType\": \"{EscapeJson(info.deviceType)}\",");
            sb.AppendLine($"        \"operatingSystem\": \"{EscapeJson(info.operatingSystem)}\",");
            sb.AppendLine($"        \"processorType\": \"{EscapeJson(info.processorType)}\",");
            sb.AppendLine($"        \"processorCount\": {info.processorCount},");
            sb.AppendLine($"        \"systemMemorySize\": {info.systemMemorySize},");
            sb.AppendLine($"        \"graphicsDeviceName\": \"{EscapeJson(info.graphicsDeviceName)}\",");
            sb.AppendLine($"        \"graphicsDeviceVendor\": \"{EscapeJson(info.graphicsDeviceVendor)}\",");
            sb.AppendLine($"        \"graphicsDeviceVersion\": \"{EscapeJson(info.graphicsDeviceVersion)}\",");
            sb.AppendLine($"        \"graphicsMemorySize\": {info.graphicsMemorySize},");
            sb.AppendLine($"        \"graphicsShaderLevel\": {info.graphicsShaderLevel},");
            sb.AppendLine($"        \"maxTextureSize\": {info.maxTextureSize},");
            sb.AppendLine($"        \"supportsVr\": {info.supportsVr.ToString().ToLower()},");
            sb.AppendLine($"        \"xrDeviceActive\": {info.xrDeviceActive.ToString().ToLower()},");
            sb.AppendLine($"        \"xrDeviceName\": \"{EscapeJson(info.xrDeviceName)}\",");
            sb.AppendLine($"        \"xrRenderViewportScale\": {info.xrRenderViewportScale:F3},");
            sb.AppendLine($"        \"screenResolution\": \"{EscapeJson(info.screenResolution)}\",");
            sb.AppendLine($"        \"screenDpi\": {info.screenDpi:F1},");
            sb.AppendLine($"        \"targetFrameRate\": {info.targetFrameRate}");
            sb.AppendLine("      }");
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
    }
}

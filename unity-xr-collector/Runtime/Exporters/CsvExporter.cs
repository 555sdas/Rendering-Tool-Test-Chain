using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using XRDataCollector.Core;
using XRDataCollector.Data;

namespace XRDataCollector.Exporters
{
    /// <summary>
    /// CSV 数据导出器
    /// 将性能数据导出为 CSV 格式文件
    /// </summary>
    public class CsvExporter : IDataExporter
    {
        #region IDataExporter Implementation

        /// <summary>
        /// 导出器名称
        /// </summary>
        public string ExporterName => "CSV";

        /// <summary>
        /// 导出文件扩展名
        /// </summary>
        public string FileExtension => ".csv";

        /// <summary>
        /// 导出性能数据为 CSV 格式
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

            var csv = BuildCsv(samples, session);
            File.WriteAllText(filePath, csv, Encoding.UTF8);
        }

        #endregion

        #region Private Methods

        private string BuildCsv(List<PerformanceSample> samples, XRTestSession session)
        {
            var sb = new StringBuilder();

            AppendSessionHeader(sb, session);
            sb.AppendLine();
            AppendColumnHeaders(sb);

            foreach (var sample in samples)
            {
                AppendSampleRow(sb, sample);
            }

            return sb.ToString();
        }

        private void AppendSessionHeader(StringBuilder sb, XRTestSession session)
        {
            if (session == null) return;

            sb.AppendLine($"# Session: {EscapeCsv(session.SessionName)}");
            sb.AppendLine($"# Session ID: {session.SessionId}");
            sb.AppendLine($"# Start Time: {session.StartTime:O}");
            sb.AppendLine($"# End Time: {session.EndTime?.ToString("O") ?? "N/A"}");
            sb.AppendLine($"# Duration: {session.ElapsedTime.TotalSeconds:F3}s");
            sb.AppendLine($"# Unity Version: {EscapeCsv(session.UnityVersion)}");
            sb.AppendLine($"# Product: {EscapeCsv(session.ProductName)}");
            sb.AppendLine($"# App Version: {EscapeCsv(session.AppVersion)}");
            sb.AppendLine($"# Platform: {EscapeCsv(session.Platform)}");
        }

        private void AppendColumnHeaders(StringBuilder sb)
        {
            sb.AppendLine(
                "Timestamp," +
                "ElapsedTime(s)," +
                "CollectionPhase," +
                "FrameRate(FPS)," +
                "FrameTime(ms)," +
                "RawFrameTime(ms)," +
                "CPUUsage(%)," +
                "GPUUsage(%)," +
                "DrawCalls," +
                "Triangles," +
                "Vertices," +
                "TotalMemory(MB)," +
                "ManagedMemory(MB)," +
                "GraphicsMemory(MB)," +
                "SystemMemory(MB)," +
                "XRActive," +
                "XRDeviceName," +
                "ActiveLights," +
                "RealtimeLights," +
                "ShadowCasters," +
                "ReflectionProbes," +
                "Materials," +
                "UniqueMaterials," +
                "TransparentMaterials," +
                "PostProcessVolumes," +
                "RenderTextures," +
                "Rigidbodies," +
                "Colliders," +
                "DeviceModel," +
                "OperatingSystem," +
                "ProcessorType," +
                "GraphicsDeviceName"
            );
        }

        private void AppendSampleRow(StringBuilder sb, PerformanceSample sample)
        {
            sb.Append($"{sample.timestamp:O},");
            sb.Append($"{sample.elapsedTime.TotalSeconds:F3},");
            sb.Append($"{EscapeCsv(sample.collectionPhase ?? "")},");
            sb.Append($"{sample.frameRate:F2},");
            sb.Append($"{sample.frameTimeMs:F3},");
            sb.Append($"{sample.rawFrameTimeMs:F3},");
            sb.Append($"{sample.cpuUsagePercent:F2},");
            sb.Append($"{sample.gpuUsagePercent:F2},");
            sb.Append($"{sample.drawCalls},");
            sb.Append($"{sample.triangles},");
            sb.Append($"{sample.vertices},");
            sb.Append($"{sample.totalMemoryMB:F2},");
            sb.Append($"{sample.managedMemoryMB:F2},");
            sb.Append($"{sample.graphicsMemoryMB:F2},");
            sb.Append($"{sample.systemMemoryMB:F2},");
            sb.Append($"{sample.isXrActive},");
            sb.Append($"{EscapeCsv(sample.xrDeviceName ?? "")},");
            sb.Append($"{sample.activeLightCount},");
            sb.Append($"{sample.realtimeLightCount},");
            sb.Append($"{sample.shadowCasterCount},");
            sb.Append($"{sample.reflectionProbeCount},");
            sb.Append($"{sample.materialCount},");
            sb.Append($"{sample.uniqueMaterialCount},");
            sb.Append($"{sample.transparentMaterialCount},");
            sb.Append($"{sample.postProcessVolumeCount},");
            sb.Append($"{sample.renderTextureCount},");
            sb.Append($"{sample.rigidbodyCount},");
            sb.Append($"{sample.colliderCount},");

            if (sample.deviceInfo != null)
            {
                sb.Append($"{EscapeCsv(sample.deviceInfo.deviceModel)},");
                sb.Append($"{EscapeCsv(sample.deviceInfo.operatingSystem)},");
                sb.Append($"{EscapeCsv(sample.deviceInfo.processorType)},");
                sb.Append($"{EscapeCsv(sample.deviceInfo.graphicsDeviceName)}");
            }
            else
            {
                sb.Append(",,,,");
            }

            sb.AppendLine();
        }

        private string EscapeCsv(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;

            bool needsQuotes = value.Contains(",") || value.Contains("\"") || value.Contains("\n") || value.Contains("\r");

            if (!needsQuotes)
                return value;

            return "\"" + value.Replace("\"", "\"\"") + "\"";
        }

        #endregion
    }
}

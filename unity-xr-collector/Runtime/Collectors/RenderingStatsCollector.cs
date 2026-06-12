using UnityEngine;
using XRDataCollector.Data;

#if UNITY_EDITOR
using UnityEditor;
#endif

#if !UNITY_EDITOR
using Unity.Profiling;
#endif

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 渲染统计采集器
    /// 采集 Draw Call、三角面、顶点数量。
    /// Editor 下使用 UnityStats（避免 ProfilerRecorder 跨域释放告警）；
    /// Player 构建使用 ProfilerRecorder。
    /// </summary>
    public class RenderingStatsCollector : IPerformanceCollector
    {
#if !UNITY_EDITOR
        private ProfilerRecorder drawCallsRecorder;
        private ProfilerRecorder trianglesRecorder;
        private ProfilerRecorder verticesRecorder;
#endif

        public string CollectorName => "RenderingStats";

        public void StartCollecting()
        {
#if !UNITY_EDITOR
            DisposeRecorders();
            drawCallsRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Draw Calls Count");
            trianglesRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Triangles Count");
            verticesRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Vertices Count");
#endif
        }

        public void StopCollecting()
        {
#if !UNITY_EDITOR
            DisposeRecorders();
#endif
        }

        public void Collect(ref PerformanceSample sample)
        {
            sample.drawCalls = ReadDrawCalls();
            sample.triangles = ReadTriangles();
            sample.vertices = ReadVertices();
        }

        private int ReadDrawCalls()
        {
#if UNITY_EDITOR
            int value = UnityStats.drawCalls;
            return value > 0 ? value : EstimateDrawCalls();
#else
            return ReadRecorderValue(drawCallsRecorder);
#endif
        }

        private int ReadTriangles()
        {
#if UNITY_EDITOR
            int value = UnityStats.triangles;
            return value > 0 ? value : EstimateGeometry(triangles: true);
#else
            return ReadRecorderValue(trianglesRecorder);
#endif
        }

        private int ReadVertices()
        {
#if UNITY_EDITOR
            int value = UnityStats.vertices;
            return value > 0 ? value : EstimateGeometry(triangles: false);
#else
            return ReadRecorderValue(verticesRecorder);
#endif
        }

#if UNITY_EDITOR
        private static int EstimateDrawCalls()
        {
            int count = 0;
            foreach (var renderer in Object.FindObjectsOfType<Renderer>())
            {
                if (renderer != null && renderer.enabled && renderer.gameObject.activeInHierarchy)
                    count += Mathf.Max(1, renderer.sharedMaterials.Length);
            }
            return count;
        }

        private static int EstimateGeometry(bool triangles)
        {
            long total = 0;
            foreach (var filter in Object.FindObjectsOfType<MeshFilter>())
            {
                var mesh = filter != null ? filter.sharedMesh : null;
                if (mesh == null) continue;
                total += triangles ? GetTriangleCount(mesh) : mesh.vertexCount;
            }
            foreach (var renderer in Object.FindObjectsOfType<SkinnedMeshRenderer>())
            {
                var mesh = renderer != null ? renderer.sharedMesh : null;
                if (mesh == null) continue;
                total += triangles ? GetTriangleCount(mesh) : mesh.vertexCount;
            }
            return total > int.MaxValue ? int.MaxValue : (int)total;
        }

        private static long GetTriangleCount(Mesh mesh)
        {
            long indices = 0;
            for (int subMesh = 0; subMesh < mesh.subMeshCount; subMesh++)
                indices += (long)mesh.GetIndexCount(subMesh);
            return indices / 3;
        }
#endif

#if !UNITY_EDITOR
        private static int ReadRecorderValue(ProfilerRecorder recorder)
        {
            if (!recorder.Valid || recorder.Count <= 0)
                return 0;

            long value = recorder.LastValue;
            return value > 0 ? (int)value : 0;
        }

        private void DisposeRecorders()
        {
            drawCallsRecorder = DisposeRecorder(drawCallsRecorder);
            trianglesRecorder = DisposeRecorder(trianglesRecorder);
            verticesRecorder = DisposeRecorder(verticesRecorder);
        }

        private static ProfilerRecorder DisposeRecorder(ProfilerRecorder recorder)
        {
            if (!recorder.Valid)
                return default;

            try
            {
                recorder.Dispose();
            }
            catch
            {
                // 域卸载期间 Dispose 可能失败，忽略即可。
            }

            return default;
        }
#endif
    }
}

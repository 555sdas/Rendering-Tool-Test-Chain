using System.Collections.Generic;
using XRDataCollector.Core;
using XRDataCollector.Data;

namespace XRDataCollector.Exporters
{
    /// <summary>
    /// 数据导出器接口
    /// 定义数据导出的标准契约
    /// </summary>
    public interface IDataExporter
    {
        /// <summary>
        /// 导出器名称
        /// </summary>
        string ExporterName { get; }

        /// <summary>
        /// 导出文件扩展名
        /// </summary>
        string FileExtension { get; }

        /// <summary>
        /// 导出性能数据到指定文件
        /// </summary>
        /// <param name="samples">性能样本列表</param>
        /// <param name="session">测试会话信息</param>
        /// <param name="filePath">目标文件路径</param>
        void Export(List<PerformanceSample> samples, XRTestSession session, string filePath);
    }
}

using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 性能数据采集器接口
    /// 所有性能数据采集器必须实现此接口
    /// </summary>
    public interface IPerformanceCollector
    {
        /// <summary>
        /// 采集器名称
        /// </summary>
        string CollectorName { get; }

        /// <summary>
        /// 开始采集
        /// 在测试会话开始时调用，用于初始化采集器状态
        /// </summary>
        void StartCollecting();

        /// <summary>
        /// 停止采集
        /// 在测试会话结束时调用，用于清理资源
        /// </summary>
        void StopCollecting();

        /// <summary>
        /// 执行一次数据采集
        /// 将采集到的数据填充到 PerformanceSample 中
        /// </summary>
        /// <param name="sample">性能样本引用，采集器将数据写入此对象</param>
        void Collect(ref PerformanceSample sample);
    }
}

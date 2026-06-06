using System;
using System.Collections.Generic;

namespace XRDataCollector.Data
{
    [Serializable]
    public class PlatformProject
    {
        public int id;
        public string name;
        public int next_session_index;
        public string DisplayName => string.IsNullOrEmpty(name) ? $"Project #{id}" : name;
    }

    [Serializable]
    public class PlatformProjectListResponse
    {
        public List<PlatformProject> items;
    }
}

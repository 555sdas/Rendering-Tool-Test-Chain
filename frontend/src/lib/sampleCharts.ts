import type { PerformanceSample } from '@/api/sessions';

export interface SampleChartPoint {
  time: string;
  fps: number;
  cpu: number;
  gpu: number;
  memory: number;
  vram: number;
  drawCalls: number;
}

export function buildSampleChartData(samples: PerformanceSample[]): SampleChartPoint[] {
  return samples.slice(0, 120).map((sample, index) => ({
    time: `${index}s`,
    fps: Number(sample.fps || 0),
    cpu: Number(sample.cpu_usage_percent || 0),
    gpu: Number(sample.gpu_usage_percent || 0),
    memory: Number(((sample.memory_mb || 0) / 1024).toFixed(2)),
    vram: Number((
      (sample.texture_memory_mb || sample.render_texture_memory_mb || 0) / 1024
    ).toFixed(2)),
    drawCalls: Number(sample.draw_calls || 0),
  }));
}

export function buildFrameTimeHistogram(samples: PerformanceSample[]) {
  const buckets = [
    { range: '< 11ms', min: 0, max: 11, count: 0 },
    { range: '11-13ms', min: 11, max: 13, count: 0 },
    { range: '13-16ms', min: 13, max: 16, count: 0 },
    { range: '16-20ms', min: 16, max: 20, count: 0 },
    { range: '> 20ms', min: 20, max: Number.POSITIVE_INFINITY, count: 0 },
  ];

  samples.forEach((sample) => {
    const frameTime = sample.frame_time_ms;
    if (frameTime == null || frameTime <= 0) return;
    const bucket = buckets.find((item) => frameTime >= item.min && frameTime < item.max);
    if (bucket) bucket.count += 1;
  });

  return buckets.map(({ range, count }) => ({ range, count }));
}

export function buildFrameQualityPieData(samples: PerformanceSample[]) {
  let normal = 0;
  let minor = 0;
  let severe = 0;
  let longFrame = 0;

  samples.forEach((sample) => {
    const frameTime = sample.frame_time_ms;
    if (frameTime == null || frameTime <= 0) return;
    if (frameTime > 33.33) {
      severe += 1;
      longFrame += 1;
    } else if (frameTime > 16.67) {
      minor += 1;
    } else {
      normal += 1;
    }
  });

  return [
    { name: '正常帧', value: normal, color: '#10b981' },
    { name: '轻微掉帧', value: minor, color: '#f59e0b' },
    { name: '严重掉帧', value: severe, color: '#ef4444' },
    { name: '长帧', value: longFrame, color: '#8b5cf6' },
  ].filter((item) => item.value > 0);
}

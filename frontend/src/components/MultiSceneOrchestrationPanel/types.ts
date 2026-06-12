import type { TestScope } from '@/lib/testScope';

export interface SceneRunDraft {
  clientId: string;
  sceneResourceId: string;
  sceneName: string;
  scenePath: string;
  projectPath: string;
  testScope: TestScope;
  collectInterval: number;
  frameRateDurationSeconds: number;
  metricsDurationSeconds: number;
}

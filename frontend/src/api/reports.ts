import apiClient from './client';

export interface TestReport {
  id: number;
  title: string;
  description: string | null;
  project_id: number | null;
  test_session_ids: number[] | null;
  creator_id: number | null;
  format: string;
  file_path: string | null;
  file_size: number | null;
  summary: Record<string, unknown> | null;
  generated_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface GenerateSessionReportRequest {
  title?: string;
  description?: string;
}

export interface ReportDownload {
  blob: Blob;
  filename: string | null;
}

function extractFilename(contentDisposition: string | undefined): string | null {
  if (!contentDisposition) {
    return null;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return filenameMatch?.[1] || null;
}

export const reportsApi = {
  generateFromSession: async (
    sessionId: number,
    data?: GenerateSessionReportRequest,
  ): Promise<TestReport> => {
    const response = await apiClient.post<TestReport>(`/test-reports/generate-from-session/${sessionId}`, data || {});
    return response.data;
  },

  download: async (reportId: number): Promise<ReportDownload> => {
    const response = await apiClient.get<Blob>(`/test-reports/${reportId}/download`, {
      responseType: 'blob',
    });
    return {
      blob: response.data,
      filename: extractFilename(response.headers['content-disposition']),
    };
  },
};

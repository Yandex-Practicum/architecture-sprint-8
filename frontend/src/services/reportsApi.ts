// src/services/reportsApi.ts
import api from './api';

export interface ReportResponse {
  reportId: string;
  cdnUrl: string;
  fromCache: boolean;
  generatedAt: string;
  cachedUntil: string;
}

// Тип данных для отчета
export interface ReportData {
  userId: string;
  userName: string;
  userEmail: string;
  reports: ReportItem[];
  summary: ReportSummary;
  generatedAt: string;
}

export interface ReportItem {
  prosthesisId: string;
  prosthesisType: string;
  reportDate: string;
  avgReactionTimeMs: number;
  maxReactionTimeMs: number;
  minReactionTimeMs: number;
  totalSignals: number;
  successfulMovements: number;
  failedMovements: number;
  misclassificationRate: number;
  avgBatteryLevel: number;
  minBatteryLevel: number;
  qualityOk: boolean;
  tuningCount: number;
  lastTuningDate: string;
}

export interface ReportSummary {
  overallAvgReactionTime: number;
  overallSuccessRate: number;
  totalMovements: number;
  daysWithData: number;
  recommendation: string;
}

class ReportsApi {
  private baseUrl = '/reports';

  async getMyReport(): Promise<ReportData> {
    const response = await api.get<ReportData>(`${this.baseUrl}/my`);
    return response.data;
  }

  async getMinioReport(dateFrom: string, dateTo: string): Promise<ReportResponse> {
    const response = await api.get<ReportResponse>(`${this.baseUrl}/minio`, {
      params: { dateFrom, dateTo }
    });
    return response.data;
  }

  async fetchReportData(cdnUrl: string): Promise<ReportData> {
    const response = await fetch(cdnUrl);
    if (!response.ok) {
      throw new Error(`Failed to fetch report: ${response.status}`);
    }
    return response.json();
  }

}



export const reportsApi = new ReportsApi();
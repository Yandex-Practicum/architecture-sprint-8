// src/services/reportsApi.ts
import api from './api';

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
}

export const reportsApi = new ReportsApi();
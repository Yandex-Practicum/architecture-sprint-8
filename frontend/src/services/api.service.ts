import { apiClient } from './auth.service';

export interface Report {
    id: number;
    name: string;
    date: string;
}

export interface ReportsResponse {
    user: string;
    reports: Report[];
}

export class ApiService {
    /**
     * Получить список отчетов
     */
    static async getReports(): Promise<ReportsResponse> {
        try {
            const response = await apiClient.get<ReportsResponse>('/api/reports');
            return response.data;
        } catch (error: any) {
            if (error.response?.status === 401) {
                // Сессия истекла - нужна повторная авторизация
                throw new Error('UNAUTHORIZED');
            }
            throw error;
        }
    }

    /**
     * Скачать отчет (пример)
     */
    static async downloadReport(reportId: number): Promise<Blob> {
        try {
            const response = await apiClient.get(`/api/reports/${reportId}/download`, {
                responseType: 'blob',
            });
            return response.data;
        } catch (error) {
            console.error('Failed to download report:', error);
            throw error;
        }
    }
}

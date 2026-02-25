import { apiClient } from './auth.service';

export interface Report {
    id: number;
    name: string;
    date: string;
}

export interface TelemetrySummary {
    prosthesis_type: string;
    muscle_group: string;
    total_signals: number;
    avg_signal_frequency: number;
    avg_signal_duration: number;
    avg_signal_amplitude: number;
    min_signal_amplitude: number;
    max_signal_amplitude: number;
    total_signal_duration: number;
    first_signal_time: string;
    last_signal_time: string;
}

export interface ReportData {
    customer_id: number;
    customer_name: string;
    email: string;
    age: number;
    gender: string;
    country: string;
    telemetry_summary: TelemetrySummary[];
    report_generated_at: string;
    data_updated_at: string;
    datamart_last_updated?: string;
}

export interface ReportsResponse {
    user: string;
    reports: Report[];
    report_data?: ReportData | null;
    message?: string;
}

export interface GenerateReportResponse {
    status: string;
    report: ReportData;
}

export class ApiService {
    /**
     * Получить список отчётов текущего пользователя
     */
    static async getReports(): Promise<ReportsResponse> {
        try {
            const response = await apiClient.get<ReportsResponse>('/api/reports');
            return response.data;
        } catch (error: any) {
            if (error.response?.status === 401) {
                throw new Error('UNAUTHORIZED');
            }
            throw error;
        }
    }

    /**
     * Сгенерировать отчёт для текущего пользователя из OLAP
     */
    static async generateReport(): Promise<GenerateReportResponse> {
        try {
            const response = await apiClient.post<GenerateReportResponse>('/api/reports/generate');
            return response.data;
        } catch (error: any) {
            if (error.response?.status === 401) {
                throw new Error('UNAUTHORIZED');
            }
            if (error.response?.status === 404) {
                const data = error.response.data;
                if (data.error === 'DATA_NOT_READY') {
                    throw new Error('DATA_NOT_READY');
                }
                if (data.error === 'NO_DATA') {
                    throw new Error(data.message || 'Данные не найдены');
                }
            }
            throw error;
        }
    }
}

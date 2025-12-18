/**
 * Сервис для работы с отчётами через Reports Service API
 */

import { createBFFAuthService } from '../auth/BFFAuthService';

export interface TelemetryMetrics {
  avg_signal_frequency: number;
  max_signal_frequency: number;
  min_signal_frequency: number;
  total_signal_duration: number;
  avg_signal_duration: number;
  avg_signal_amplitude: number;
  max_signal_amplitude: number;
  avg_battery_level: number;
  min_battery_level: number;
  avg_movement_accuracy: number;
  total_movements: number;
}

export interface UsageStatistics {
  usage_intensity: 'Low' | 'Medium' | 'High' | 'Very High';
  battery_health: 'Critical' | 'Low' | 'Good' | 'Excellent';
  data_quality_score: number;
  primary_muscle_group: string;
  prosthesis_type: string;
}

export interface DailyMetrics {
  report_date: string;
  telemetry: TelemetryMetrics;
  usage: UsageStatistics;
}

export interface UserInfo {
  user_id: number;
  customer_name: string;
  email: string;
  age: number;
  gender: string;
  country: string;
}

export interface UserReport {
  user_info: UserInfo;
  report_period: {
    start_date: string;
    end_date: string;
  };
  summary_metrics: TelemetryMetrics;
  summary_usage: UsageStatistics;
  daily_metrics: DailyMetrics[];
  insights: string[];
  recommendations: string[];
  generated_at: string;
}

export interface UserSummary {
  user_id: number;
  customer_name: string;
  prosthesis_type: string;
  total_movements: number;
  usage_intensity: string;
  data_quality_score: number;
  last_activity_date: string;
}

export interface DataAvailability {
  reports_available: boolean;
  latest_report_date: string | null;
  total_reports: number;
  telemetry_data_available: boolean;
}

export class ReportsService {
  private reportsApiUrl: string;
  private authService = createBFFAuthService();

  constructor() {
    // Используем BFF для проксирования запросов к Reports Service
    this.reportsApiUrl = process.env.REACT_APP_BFF_URL || 'http://localhost:5001';
  }

  /**
   * Получение отчёта пользователя
   */
  async getUserReport(
    userId: number,
    startDate?: string,
    endDate?: string
  ): Promise<UserReport> {
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);

      const queryString = params.toString();
      const url = `${this.reportsApiUrl}/api/reports/user/${userId}${queryString ? '?' + queryString : ''}`;

      const response = await this.authService.fetchProtected(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Доступ запрещён. Вы можете просматривать только свои отчёты.');
        } else if (response.status === 404) {
          throw new Error('Отчёт не найден для указанного периода.');
        } else {
          throw new Error(`Ошибка получения отчёта: ${response.status}`);
        }
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching user report:', error);
      throw error;
    }
  }

  /**
   * Получение краткой сводки пользователя
   */
  async getUserSummary(userId: number): Promise<UserSummary> {
    try {
      const response = await this.authService.fetchProtected(
        `${this.reportsApiUrl}/api/reports/user/${userId}/summary`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Доступ запрещён. Вы можете просматривать только свои данные.');
        } else {
          throw new Error(`Ошибка получения сводки: ${response.status}`);
        }
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching user summary:', error);
      throw error;
    }
  }


  /**
   * Получение информации о доступности данных
   */
  async getDataAvailability(): Promise<DataAvailability> {
    try {
      const response = await this.authService.fetchProtected(
        `${this.reportsApiUrl}/api/reports/data-availability`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Ошибка получения информации о данных: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching data availability:', error);
      throw error;
    }
  }


  /**
   * Форматирование даты для API
   */
  formatDate(date: Date): string {
    return date.toISOString().split('T')[0];
  }

  /**
   * Получение даты N дней назад
   */
  getDaysAgo(days: number): Date {
    const date = new Date();
    date.setDate(date.getDate() - days);
    return date;
  }
}

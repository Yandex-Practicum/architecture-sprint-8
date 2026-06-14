/**
 * TypeScript types for Reports API responses
 */

// Hourly statistics
export interface HourlyStats {
  hour: number;
  movements_count: number;
  successful_movements: number;
  success_rate: number;
  avg_response_time: number;
  avg_battery_level: number;
  error_count: number;
}

// Report summary in list
export interface ReportSummary {
  report_date: string;
  total_movements: number;
  total_errors: number;
  active_hours: number;
}

// Daily report detail
export interface DailyReport {
  report_date: string;
  user_id: string;
  customer_name: string;
  prosthesis_id: number;
  prosthesis_model: string;
  prosthesis_serial: string;
  customer_region: string;
  total_movements: number;
  total_successful: number;
  daily_success_rate: number;
  avg_response_time: number;
  avg_battery_level: number;
  min_battery_level: number;
  max_actuator_temp: number;
  total_errors: number;
  active_hours: number;
  hourly_stats?: HourlyStats[];
}

// User reports list
export interface UserReportsList {
  user_id: string;
  customer_name: string;
  prosthesis_model: string;
  total_reports: number;
  date_range: {
    first_date: string | null;
    last_date: string | null;
  };
  reports: ReportSummary[];
}

// User summary
export interface UserSummary {
  user_id: string;
  customer_name: string;
  prosthesis_model: string;
  prosthesis_serial: string;
  customer_region: string;
  first_activity_date: string;
  last_activity_date: string;
  total_days: number;
  active_days: number;
  total_movements: number;
  total_successful: number;
  overall_success_rate: number;
  avg_response_time: number;
  avg_battery_level: number;
  total_errors: number;
  avg_errors_per_day: number;
}

// API responses
export interface ReportsListResponse {
  success: boolean;
  data: UserReportsList;
}

export interface ReportDetailResponse {
  success: boolean;
  data: DailyReport;
}

export interface UserSummaryResponse {
  success: boolean;
  data: UserSummary;
}

export interface ErrorResponse {
  success: boolean;
  error: string;
  detail?: string;
}

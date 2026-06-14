import React from 'react';
import { DailyReport, HourlyStats } from '../../types/reports';

interface DailyReportViewProps {
  report: DailyReport;
  onBack: () => void;
}

/**
 * Detailed daily report view with hourly breakdown
 */
const DailyReportView: React.FC<DailyReportViewProps> = ({ report, onBack }) => {
  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getSuccessRateColor = (rate: number): string => {
    if (rate >= 95) return 'text-green-600';
    if (rate >= 85) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getBatteryColor = (level: number): string => {
    if (level >= 50) return 'bg-green-500';
    if (level >= 20) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center text-blue-600 hover:text-blue-800 transition-colors"
        >
          <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Reports
        </button>
      </div>

      {/* Report Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          {formatDate(report.report_date)}
        </h2>
        <div className="text-gray-600">
          <p>{report.customer_name}</p>
          <p className="text-sm">{report.prosthesis_model} ({report.prosthesis_serial})</p>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Total Movements"
          value={report.total_movements.toLocaleString()}
          icon="📊"
        />
        <MetricCard
          title="Success Rate"
          value={`${report.daily_success_rate.toFixed(1)}%`}
          icon="✓"
          valueColor={getSuccessRateColor(report.daily_success_rate)}
        />
        <MetricCard
          title="Avg Response Time"
          value={`${report.avg_response_time.toFixed(0)}ms`}
          icon="⚡"
        />
        <MetricCard
          title="Active Hours"
          value={`${report.active_hours}h`}
          icon="🕐"
        />
      </div>

      {/* Battery & Temperature */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-medium text-gray-900 mb-3">Battery Level</h3>
          <div className="flex items-center space-x-4">
            <div className="flex-1">
              <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full ${getBatteryColor(report.avg_battery_level)} transition-all`}
                  style={{ width: `${report.avg_battery_level}%` }}
                />
              </div>
            </div>
            <span className="text-lg font-semibold">{report.avg_battery_level.toFixed(0)}%</span>
          </div>
          <p className="text-sm text-gray-500 mt-2">
            Min: {report.min_battery_level}%
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-medium text-gray-900 mb-3">Actuator Temperature</h3>
          <div className="flex items-center justify-between">
            <span className="text-3xl">🌡️</span>
            <div className="text-right">
              <p className="text-2xl font-semibold">{report.max_actuator_temp.toFixed(1)}°C</p>
              <p className="text-sm text-gray-500">Maximum</p>
            </div>
          </div>
        </div>
      </div>

      {/* Errors */}
      {report.total_errors > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="font-medium text-red-800 mb-2">Errors Detected</h3>
          <p className="text-red-700">
            {report.total_errors} error{report.total_errors !== 1 ? 's' : ''} occurred during this day.
            Please contact support if issues persist.
          </p>
        </div>
      )}

      {/* Hourly Breakdown */}
      {report.hourly_stats && report.hourly_stats.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-medium text-gray-900 mb-4">Hourly Activity</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3">Hour</th>
                  <th className="text-right py-2 px-3">Movements</th>
                  <th className="text-right py-2 px-3">Success Rate</th>
                  <th className="text-right py-2 px-3">Avg Response</th>
                  <th className="text-right py-2 px-3">Battery</th>
                  <th className="text-right py-2 px-3">Errors</th>
                </tr>
              </thead>
              <tbody>
                {report.hourly_stats.map((hour: HourlyStats) => (
                  <tr key={hour.hour} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium">
                      {hour.hour.toString().padStart(2, '0')}:00
                    </td>
                    <td className="text-right py-2 px-3">{hour.movements_count}</td>
                    <td className={`text-right py-2 px-3 ${getSuccessRateColor(hour.success_rate)}`}>
                      {hour.success_rate.toFixed(1)}%
                    </td>
                    <td className="text-right py-2 px-3">{hour.avg_response_time.toFixed(0)}ms</td>
                    <td className="text-right py-2 px-3">{hour.avg_battery_level.toFixed(0)}%</td>
                    <td className="text-right py-2 px-3">
                      {hour.error_count > 0 ? (
                        <span className="text-red-600">{hour.error_count}</span>
                      ) : (
                        <span className="text-green-600">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Metric card component
 */
interface MetricCardProps {
  title: string;
  value: string;
  icon: string;
  valueColor?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, icon, valueColor = 'text-gray-900' }) => (
  <div className="bg-white rounded-lg shadow p-4">
    <div className="flex items-center justify-between mb-2">
      <span className="text-2xl">{icon}</span>
    </div>
    <p className="text-sm text-gray-500">{title}</p>
    <p className={`text-xl font-semibold ${valueColor}`}>{value}</p>
  </div>
);

export default DailyReportView;

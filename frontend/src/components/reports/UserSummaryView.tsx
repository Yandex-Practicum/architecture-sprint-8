import React from 'react';
import { UserSummary } from '../../types/reports';

interface UserSummaryViewProps {
  summary: UserSummary;
}

/**
 * User summary card showing all-time statistics
 */
const UserSummaryView: React.FC<UserSummaryViewProps> = ({ summary }) => {
  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getSuccessRateColor = (rate: number): string => {
    if (rate >= 95) return 'text-green-600';
    if (rate >= 85) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg shadow-lg p-6 text-white">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="text-xl font-bold">{summary.customer_name}</h2>
          <p className="text-blue-100">{summary.prosthesis_model}</p>
          <p className="text-sm text-blue-200">{summary.prosthesis_serial}</p>
        </div>
        <span className="px-3 py-1 bg-white bg-opacity-20 rounded-full text-sm">
          {summary.customer_region}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
        <div className="bg-white bg-opacity-10 rounded-lg p-3">
          <p className="text-blue-100 text-sm">Total Movements</p>
          <p className="text-2xl font-bold">{summary.total_movements.toLocaleString()}</p>
        </div>

        <div className="bg-white bg-opacity-10 rounded-lg p-3">
          <p className="text-blue-100 text-sm">Success Rate</p>
          <p className={`text-2xl font-bold ${summary.overall_success_rate >= 95 ? 'text-green-300' : 'text-yellow-300'}`}>
            {summary.overall_success_rate.toFixed(1)}%
          </p>
        </div>

        <div className="bg-white bg-opacity-10 rounded-lg p-3">
          <p className="text-blue-100 text-sm">Active Days</p>
          <p className="text-2xl font-bold">
            {summary.active_days}
            <span className="text-sm font-normal text-blue-200">/{summary.total_days}</span>
          </p>
        </div>

        <div className="bg-white bg-opacity-10 rounded-lg p-3">
          <p className="text-blue-100 text-sm">Avg Response</p>
          <p className="text-2xl font-bold">{summary.avg_response_time.toFixed(0)}ms</p>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-white border-opacity-20 flex justify-between text-sm text-blue-100">
        <span>First activity: {formatDate(summary.first_activity_date)}</span>
        <span>Last activity: {formatDate(summary.last_activity_date)}</span>
      </div>
    </div>
  );
};

export default UserSummaryView;

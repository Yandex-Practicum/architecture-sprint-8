import React from 'react';
import { ReportSummary } from '../../types/reports';

interface ReportCardProps {
  report: ReportSummary;
  onSelect: (date: string) => void;
}

/**
 * Card displaying a report summary with click to view details
 */
const ReportCard: React.FC<ReportCardProps> = ({ report, onSelect }) => {
  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStatusColor = (errors: number): string => {
    if (errors === 0) return 'bg-green-100 text-green-800';
    if (errors < 5) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  return (
    <div
      onClick={() => onSelect(report.report_date)}
      className="p-4 bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md hover:border-blue-300 cursor-pointer transition-all"
    >
      <div className="flex justify-between items-start mb-3">
        <h3 className="font-medium text-gray-900">{formatDate(report.report_date)}</h3>
        <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(report.total_errors)}`}>
          {report.total_errors === 0 ? 'OK' : `${report.total_errors} errors`}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-gray-500">Movements</p>
          <p className="font-semibold text-gray-900">{report.total_movements.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-gray-500">Active Hours</p>
          <p className="font-semibold text-gray-900">{report.active_hours}h</p>
        </div>
      </div>

      <div className="mt-3 text-right">
        <span className="text-blue-600 text-sm hover:underline">View Details →</span>
      </div>
    </div>
  );
};

export default ReportCard;

import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportData {
  userId: number;
  email: string;
  firstName: string;
  lastName: string;
  prosthesisId: string;
  reportDate: string;
  totalActions: number;
  avgResponseTime: number;
  maxResponseTime: number;
  minResponseTime: number;
  graspCount: number;
  releaseCount: number;
  flexCount: number;
  avgBatteryLevel: number;
  minBatteryLevel: number;
  totalUsageSeconds: number;
  usageHours: number;
  actionsPerHour: number;
  efficiencyScore: number;
  orderDate: string;
  status: string;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reports, setReports] = useState<ReportData[]>([]);
  const [showReports, setShowReports] = useState(false);

  const fetchReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Access denied. You can only view your own reports.');
        }
        throw new Error(`Failed to fetch report: ${response.statusText}`);
      }

      const data: ReportData[] = await response.json();
      setReports(data);
      setShowReports(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setShowReports(false);
    } finally {
      setLoading(false);
    }
  };

  const downloadReportAsCSV = () => {
    if (reports.length === 0) return;

    const headers = [
      'Date', 'Total Actions', 'Avg Response Time (ms)', 'Max Response Time (ms)',
      'Min Response Time (ms)', 'Grasp Count', 'Release Count', 'Flex Count',
      'Avg Battery Level (%)', 'Min Battery Level (%)', 'Usage Hours',
      'Actions Per Hour', 'Efficiency Score'
    ];

    const rows = reports.map(report => [
      report.reportDate,
      report.totalActions,
      report.avgResponseTime.toFixed(2),
      report.maxResponseTime.toFixed(2),
      report.minResponseTime.toFixed(2),
      report.graspCount,
      report.releaseCount,
      report.flexCount,
      report.avgBatteryLevel.toFixed(2),
      report.minBatteryLevel.toFixed(2),
      report.usageHours.toFixed(2),
      report.actionsPerHour.toFixed(2),
      report.efficiencyScore.toFixed(2)
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `prosthesis-report-${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center min-h-screen bg-gray-100 py-8">
      <div className="w-full max-w-6xl px-4">
        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800">Usage Reports</h1>
            {reports.length > 0 && (
              <button
                onClick={downloadReportAsCSV}
                className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition"
              >
                Download CSV
              </button>
            )}
          </div>
          
          <button
            onClick={fetchReport}
            disabled={loading}
            className={`px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Loading Report...' : 'Get Report'}
          </button>

          {error && (
            <div className="mt-4 p-4 bg-red-100 text-red-700 rounded-lg border border-red-300">
              <strong>Error:</strong> {error}
            </div>
          )}

          {showReports && reports.length > 0 && (
            <div className="mt-8">
              <h2 className="text-xl font-semibold mb-4 text-gray-700">
                Report Data ({reports.length} {reports.length === 1 ? 'entry' : 'entries'})
              </h2>
              
              <div className="overflow-x-auto">
                <table className="min-w-full bg-white border border-gray-300 rounded-lg">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">Date</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">Actions</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">Avg Response (ms)</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">Battery (%)</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">Usage (h)</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">Efficiency</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {reports.map((report, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {new Date(report.reportDate).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {report.totalActions}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {report.avgResponseTime.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {report.avgBatteryLevel.toFixed(1)}%
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {report.usageHours.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            report.efficiencyScore >= 80 ? 'bg-green-100 text-green-800' :
                            report.efficiencyScore >= 60 ? 'bg-yellow-100 text-yellow-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {report.efficiencyScore.toFixed(1)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Детальная информация по первому отчёту */}
              {reports.length > 0 && (
                <div className="mt-8 p-6 bg-gray-50 rounded-lg">
                  <h3 className="text-lg font-semibold mb-4 text-gray-700">Detailed Information</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">User</p>
                      <p className="font-medium">{reports[0].firstName} {reports[0].lastName}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Email</p>
                      <p className="font-medium">{reports[0].email}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Prosthesis ID</p>
                      <p className="font-medium">{reports[0].prosthesisId}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Grasp Actions</p>
                      <p className="font-medium">{reports[0].graspCount}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Release Actions</p>
                      <p className="font-medium">{reports[0].releaseCount}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Flex Actions</p>
                      <p className="font-medium">{reports[0].flexCount}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Min Response Time</p>
                      <p className="font-medium">{reports[0].minResponseTime.toFixed(2)} ms</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Max Response Time</p>
                      <p className="font-medium">{reports[0].maxResponseTime.toFixed(2)} ms</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Actions Per Hour</p>
                      <p className="font-medium">{reports[0].actionsPerHour.toFixed(2)}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {showReports && reports.length === 0 && !loading && (
            <div className="mt-8 p-4 bg-yellow-100 text-yellow-700 rounded-lg border border-yellow-300">
              No reports found for your account.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReportPage;
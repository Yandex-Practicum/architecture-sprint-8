import React, { useState, useEffect } from 'react';
import { ApiService, Report } from '../services/api.service';
import { AuthService } from '../services/auth.service';

interface ReportPageProps {
  user: any;
  onLogout: () => void;
}

const ReportPage: React.FC<ReportPageProps> = ({ user, onLogout }) => {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await ApiService.getReports();
      setReports(data.reports);
    } catch (err: any) {
      if (err.message === 'UNAUTHORIZED') {
        setError('Session expired. Please login again.');
        // Можно автоматически редиректить на login
        setTimeout(() => {
          AuthService.login();
        }, 2000);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load reports');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (reportId: number, reportName: string) => {
    try {
      setLoading(true);
      const blob = await ApiService.downloadReport(reportId);

      // Создание ссылки для скачивания
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${reportName}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download report');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              BionicPRO Reports
            </h1>
            {user && (
              <p className="text-sm text-gray-600 mt-1">
                Welcome, {user.preferred_username || user.name || 'User'}
              </p>
            )}
          </div>
          <button
            onClick={onLogout}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold text-gray-800">
              Your Usage Reports
            </h2>
            <button
              onClick={loadReports}
              disabled={loading}
              className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''
                }`}
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
              <p className="font-medium">Error</p>
              <p className="text-sm">{error}</p>
            </div>
          )}

          {/* Loading State */}
          {loading && reports.length === 0 && (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-4 border-blue-500 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading reports...</p>
            </div>
          )}

          {/* Reports List */}
          {!loading && reports.length === 0 && !error && (
            <div className="text-center py-8 text-gray-500">
              <p>No reports available</p>
            </div>
          )}

          {reports.length > 0 && (
            <div className="space-y-3">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div>
                    <h3 className="font-medium text-gray-900">
                      {report.name}
                    </h3>
                    <p className="text-sm text-gray-600">{report.date}</p>
                  </div>
                  <button
                    onClick={() => handleDownload(report.id, report.name)}
                    disabled={loading}
                    className={`px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''
                      }`}
                  >
                    Download
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Info Section */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-blue-400"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                <strong>Secure Session:</strong> Your connection is protected with
                HTTP-only cookies and automatic token refresh. Session will
                expire after 30 minutes of inactivity.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportPage;

import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useReports } from '../hooks/useReports';
import ReportCard from './reports/ReportCard';
import DailyReportView from './reports/DailyReportView';
import UserSummaryView from './reports/UserSummaryView';

type ViewMode = 'list' | 'detail';

/**
 * Main Reports Page Component
 *
 * Features:
 * - User summary dashboard
 * - List of available reports
 * - Detailed daily report view with hourly breakdown
 * - Authentication required
 * - User can only see their own reports (enforced by backend)
 */
const ReportPage: React.FC = () => {
  const { authenticated, initialized, user, login, logout } = useAuth();
  const {
    reportsList,
    dailyReport,
    userSummary,
    loading,
    error,
    fetchReportsList,
    fetchDailyReport,
    fetchUserSummary,
    clearCache,
    clearError,
  } = useReports();

  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Fetch reports list and summary when authenticated
  useEffect(() => {
    if (authenticated) {
      fetchReportsList();
      fetchUserSummary();
    }
  }, [authenticated, fetchReportsList, fetchUserSummary]);

  // Handle report selection
  const handleSelectReport = (date: string) => {
    setSelectedDate(date);
    setViewMode('detail');
    fetchDailyReport(date);
  };

  // Handle back to list
  const handleBackToList = () => {
    setViewMode('list');
    setSelectedDate(null);
    clearError();
  };

  // Handle refresh
  const handleRefresh = async () => {
    await clearCache();
    await fetchReportsList();
    await fetchUserSummary();
  };

  // Loading state (initial load)
  if (!initialized) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="flex items-center space-x-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          <span className="text-lg text-gray-600">Loading...</span>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md text-center max-w-md">
          <div className="mb-6">
            <svg
              className="w-16 h-16 mx-auto text-blue-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold mb-4">BionicPRO Reports</h1>
          <p className="mb-6 text-gray-600">
            Please log in to access your prosthesis usage reports.
            Your data is protected and only you can view your reports.
          </p>
          <button
            onClick={login}
            className="w-full px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium"
          >
            Login with Keycloak
          </button>
        </div>
      </div>
    );
  }

  // Authenticated - show reports
  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-bold text-gray-900">
              BionicPRO Reports
            </h1>
            <div className="flex items-center space-x-4">
              {user && (
                <span className="text-sm text-gray-600">
                  {user.preferred_username || user.email}
                </span>
              )}
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
                title="Refresh reports"
              >
                <svg
                  className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
              </button>
              <button
                onClick={logout}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-100 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex justify-between items-center">
            <div className="flex items-center">
              <svg
                className="w-5 h-5 text-red-500 mr-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-red-700">{error}</span>
            </div>
            <button
              onClick={clearError}
              className="text-red-500 hover:text-red-700"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Loading Overlay */}
        {loading && (
          <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 flex items-center space-x-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
              <span className="text-gray-700">Loading reports...</span>
            </div>
          </div>
        )}

        {/* Detail View */}
        {viewMode === 'detail' && dailyReport && (
          <DailyReportView report={dailyReport} onBack={handleBackToList} />
        )}

        {/* List View */}
        {viewMode === 'list' && (
          <div className="space-y-6">
            {/* User Summary */}
            {userSummary && <UserSummaryView summary={userSummary} />}

            {/* Reports List */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Available Reports
                </h2>
                {reportsList && (
                  <span className="text-sm text-gray-500">
                    {reportsList.total_reports} report{reportsList.total_reports !== 1 ? 's' : ''}
                  </span>
                )}
              </div>

              {reportsList && reportsList.reports.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {reportsList.reports.map((report) => (
                    <ReportCard
                      key={report.report_date}
                      report={report}
                      onSelect={handleSelectReport}
                    />
                  ))}
                </div>
              ) : !loading ? (
                <div className="text-center py-12">
                  <svg
                    className="w-16 h-16 mx-auto text-gray-300 mb-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <p className="text-gray-500">No reports available yet.</p>
                  <p className="text-sm text-gray-400 mt-2">
                    Reports are generated automatically from your prosthesis usage data.
                  </p>
                </div>
              ) : null}
            </div>

            {/* Security Notice */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start">
                <svg
                  className="w-5 h-5 text-blue-500 mt-0.5 mr-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div>
                  <h3 className="text-sm font-medium text-blue-800">Your data is protected</h3>
                  <p className="text-sm text-blue-700 mt-1">
                    You can only view your own reports. All access is logged for security purposes.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default ReportPage;

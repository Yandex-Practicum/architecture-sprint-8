/**
 * Custom hook for fetching reports from the Reports Service API.
 *
 * All requests go through bionicpro-auth proxy which:
 * - Validates the user session
 * - Injects the Bearer token
 * - Ensures user can only access their own reports
 */

import { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  UserReportsList,
  DailyReport,
  UserSummary,
  ReportsListResponse,
  ReportDetailResponse,
  UserSummaryResponse,
} from '../types/reports';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8000';

interface UseReportsReturn {
  // Data
  reportsList: UserReportsList | null;
  dailyReport: DailyReport | null;
  userSummary: UserSummary | null;

  // State
  loading: boolean;
  error: string | null;

  // Actions
  fetchReportsList: () => Promise<void>;
  fetchDailyReport: (date: string) => Promise<void>;
  fetchUserSummary: () => Promise<void>;
  clearCache: () => Promise<void>;
  clearError: () => void;
}

// Time window (ms) during which we suppress "Session expired" errors after login
const NEW_SESSION_WINDOW_MS = 30000; // 30 seconds

export const useReports = (): UseReportsReturn => {
  const { authenticated, isNewSession, sessionCreatedAt, clearNewSessionFlag } = useAuth();

  /**
   * Check if we're within the "new session" grace period
   * This prevents showing "Session expired" immediately after login
   */
  const isWithinNewSessionWindow = useCallback((): boolean => {
    if (isNewSession) return true;
    if (sessionCreatedAt && Date.now() - sessionCreatedAt < NEW_SESSION_WINDOW_MS) {
      return true;
    }
    return false;
  }, [isNewSession, sessionCreatedAt]);

  const [reportsList, setReportsList] = useState<UserReportsList | null>(null);
  const [dailyReport, setDailyReport] = useState<DailyReport | null>(null);
  const [userSummary, setUserSummary] = useState<UserSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch with authentication - uses session cookie
   */
  const fetchWithAuth = useCallback(async (url: string): Promise<Response> => {
    return fetch(`${AUTH_URL}${url}`, {
      credentials: 'include',
      headers: {
        'Accept': 'application/json',
      },
    });
  }, []);

  /**
   * Handle API errors
   */
  const handleError = useCallback((response: Response, data: any): string | null => {
    if (response.status === 401) {
      // Don't show "Session expired" on a fresh login - it's confusing
      // Use the window check for more reliable detection
      if (isWithinNewSessionWindow()) {
        return null; // Will be handled by returning empty data instead of error
      }
      return 'Session expired. Please log in again.';
    }
    if (response.status === 403) {
      return 'Access denied. You can only view your own reports.';
    }
    if (response.status === 404) {
      return data?.detail || 'No reports found.';
    }
    return data?.error || data?.detail || 'Failed to fetch reports.';
  }, [isWithinNewSessionWindow]);

  /**
   * Fetch list of available reports
   */
  const fetchReportsList = useCallback(async () => {
    if (!authenticated) {
      setError('Please log in to view reports.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth('/api/reports');
      const data = await response.json();

      // 404 is OK - just means no reports available yet
      if (response.status === 404) {
        setReportsList({
          user_id: '',
          customer_name: '',
          prosthesis_model: '',
          total_reports: 0,
          date_range: { first_date: null, last_date: null },
          reports: []
        });
        setError(null);
        // Don't clear new session flag here - other requests may still be pending
        return;
      }

      // Handle 401 on new session - treat as empty data, not error
      if (response.status === 401 && isWithinNewSessionWindow()) {
        setReportsList({
          user_id: '',
          customer_name: '',
          prosthesis_model: '',
          total_reports: 0,
          date_range: { first_date: null, last_date: null },
          reports: []
        });
        setError(null);
        // Don't clear flag here - let the timer handle it
        return;
      }

      if (!response.ok) {
        const errorMsg = handleError(response, data);
        if (errorMsg) {
          throw new Error(errorMsg);
        }
        return;
      }

      const typedData = data as ReportsListResponse;
      if (typedData.success && typedData.data) {
        setReportsList(typedData.data);
        // Successfully fetched data - can clear new session flag
        clearNewSessionFlag();
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch reports';
      setError(message);
      setReportsList(null);
    } finally {
      setLoading(false);
    }
  }, [authenticated, isWithinNewSessionWindow, fetchWithAuth, handleError, clearNewSessionFlag]);

  /**
   * Fetch detailed daily report for a specific date
   */
  const fetchDailyReport = useCallback(async (date: string) => {
    if (!authenticated) {
      setError('Please log in to view reports.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth(`/api/reports/${date}`);
      const data = await response.json();

      // Handle 401 on new session - show generic message
      if (response.status === 401 && isWithinNewSessionWindow()) {
        setDailyReport(null);
        setError(null);  // Don't show error for new session
        return;
      }

      if (!response.ok) {
        const errorMsg = handleError(response, data);
        if (errorMsg) {
          throw new Error(errorMsg);
        }
        return;
      }

      const typedData = data as ReportDetailResponse;
      if (typedData.success && typedData.data) {
        setDailyReport(typedData.data);
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch report';
      setError(message);
      setDailyReport(null);
    } finally {
      setLoading(false);
    }
  }, [authenticated, isWithinNewSessionWindow, fetchWithAuth, handleError]);

  /**
   * Fetch user summary (all-time statistics)
   */
  const fetchUserSummary = useCallback(async () => {
    if (!authenticated) {
      setError('Please log in to view reports.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth('/api/reports/summary');
      const data = await response.json();

      // 404 is OK - just means no data available yet
      if (response.status === 404) {
        setUserSummary(null);
        setError(null);
        return;
      }

      // Handle 401 on new session - treat as no data, not error
      if (response.status === 401 && isWithinNewSessionWindow()) {
        setUserSummary(null);
        setError(null);
        return;
      }

      if (!response.ok) {
        const errorMsg = handleError(response, data);
        if (errorMsg) {
          throw new Error(errorMsg);
        }
        return;
      }

      const typedData = data as UserSummaryResponse;
      if (typedData.success && typedData.data) {
        setUserSummary(typedData.data);
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch summary';
      setError(message);
      setUserSummary(null);
    } finally {
      setLoading(false);
    }
  }, [authenticated, isWithinNewSessionWindow, fetchWithAuth, handleError]);

  /**
   * Clear cached reports
   */
  const clearCache = useCallback(async () => {
    if (!authenticated) {
      return;
    }

    try {
      const response = await fetch(`${AUTH_URL}/api/reports/cache`, {
        method: 'DELETE',
        credentials: 'include',
      });

      if (response.ok) {
        // Refresh data after clearing cache
        setReportsList(null);
        setDailyReport(null);
        setUserSummary(null);
      }
    } catch (err) {
      console.error('Failed to clear cache:', err);
    }
  }, [authenticated]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
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
  };
};

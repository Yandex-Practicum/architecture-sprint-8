import React, { useEffect, useState } from 'react';

type AuthenticatedUser = {
  username: string;
  email?: string;
  fullName?: string;
  roles: string[];
  identityProvider: string;
};

type ReportAvailability = {
  availableFrom: string;
  availableTo: string;
  loadedAt: string;
};

type ReportDelivery = {
  provider: string;
  bucket: string;
  objectKey: string;
  format: string;
  fileName: string;
  cacheHit: boolean;
  cacheVersion: string;
  downloadUrl: string;
};

type ReportDeliveryResponse = {
  delivery: ReportDelivery;
};

const apiBaseUrl = process.env.REACT_APP_API_URL || '/api';

const readErrorMessage = async (response: Response) => {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    const payload = await response.json().catch(() => null);
    if (payload && typeof payload.detail === 'string') {
      return payload.detail;
    }
  }

  return response.text();
};

const defaultPeriod = (availability: ReportAvailability) => {
  const availableFrom = new Date(`${availability.availableFrom}T00:00:00`);
  const availableTo = new Date(`${availability.availableTo}T00:00:00`);
  const rangeStart = new Date(availableTo);
  rangeStart.setDate(rangeStart.getDate() - 6);

  if (rangeStart < availableFrom) {
    return {
      dateFrom: availability.availableFrom,
      dateTo: availability.availableTo
    };
  }

  return {
    dateFrom: rangeStart.toISOString().slice(0, 10),
    dateTo: availability.availableTo
  };
};

const ReportPage: React.FC = () => {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [availability, setAvailability] = useState<ReportAvailability | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  useEffect(() => {
    const loadSession = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/auth/me`, {
          credentials: 'include'
        });

        if (response.status === 401) {
          setUser(null);
          return;
        }

        if (!response.ok) {
          throw new Error('Unable to load the current session');
        }

        const payload = await response.json();
        setUser(payload.user);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load session');
      } finally {
        setAuthLoading(false);
      }
    };

    loadSession();
  }, []);

  useEffect(() => {
    const loadAvailability = async () => {
      if (!user) {
        setAvailability(null);
        setDateFrom('');
        setDateTo('');
        return;
      }

      try {
        setAvailabilityLoading(true);
        const response = await fetch(`${apiBaseUrl}/reports/availability`, {
          credentials: 'include'
        });

        if (response.status === 401) {
          setUser(null);
          setAvailability(null);
          return;
        }

        if (!response.ok) {
          const payload = await response.text();
          throw new Error(payload || 'Unable to load report availability');
        }

        const payload = await response.json();
        const nextAvailability: ReportAvailability = payload.availability;
        setAvailability(nextAvailability);
        const period = defaultPeriod(nextAvailability);
        setDateFrom(period.dateFrom);
        setDateTo(period.dateTo);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load report availability');
      } finally {
        setAvailabilityLoading(false);
      }
    };

    loadAvailability();
  }, [user]);

  const login = () => {
    window.location.href = `${apiBaseUrl}/auth/login?return_to=/`;
  };

  const logout = async () => {
    try {
      setLoading(true);
      setError(null);
      await fetch(`${apiBaseUrl}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
      setUser(null);
      setAvailability(null);
      setInfo('Session closed.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to close the session');
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async () => {
    if (!user) {
      setError('Session not found');
      return;
    }
    if (!availability || !dateFrom || !dateTo) {
      setError('Processed report period is not available yet');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setInfo(null);

      const query = new URLSearchParams({
        date_from: dateFrom,
        date_to: dateTo,
        format: 'csv'
      });
      const response = await fetch(`${apiBaseUrl}/reports?${query.toString()}`, {
        credentials: 'include'
      });

      if (response.status === 401) {
        setUser(null);
        setError('Session expired. Sign in again.');
        return;
      }

      if (!response.ok) {
        const payload = await readErrorMessage(response);
        throw new Error(payload || 'Unable to generate the report');
      }

      const payload: ReportDeliveryResponse = await response.json();
      const url = payload.delivery.downloadUrl;
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = payload.delivery.fileName;
      anchor.rel = 'noreferrer noopener';
      anchor.click();
      setInfo(
        payload.delivery.cacheHit
          ? 'Report link returned from S3/CDN cache.'
          : 'Report generated, uploaded to S3, and published through CDN.'
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return <div>Loading...</div>;
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="mb-6 max-w-md rounded-lg bg-white p-8 text-center shadow-md">
          <h1 className="mb-3 text-2xl font-bold">Usage Reports</h1>
        </div>
        <button
          onClick={login}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
        {error && (
          <div className="mt-4 rounded bg-red-100 p-4 text-red-700">
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full max-w-xl rounded-lg bg-white p-8 shadow-md">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="mb-2 text-2xl font-bold">Usage Reports</h1>
            <p className="text-sm text-gray-600">
              Signed in as <span className="font-semibold">{user.fullName || user.username}</span>
            </p>
            <p className="text-xs text-gray-500">
              Roles: {user.roles.join(', ')} | IdP: {user.identityProvider}
            </p>
            {availability && (
              <p className="mt-2 text-xs text-gray-500">
                Processed OLAP period: {availability.availableFrom} to {availability.availableTo}
              </p>
            )}
          </div>
          <button
            onClick={logout}
            disabled={loading}
            className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Logout
          </button>
        </div>

        <div className="mb-6 grid gap-4 md:grid-cols-2">
          <label className="text-sm text-gray-700">
            <span className="mb-1 block font-medium">Date From</span>
            <input
              type="date"
              value={dateFrom}
              min={availability?.availableFrom}
              max={dateTo || availability?.availableTo}
              onChange={(event) => setDateFrom(event.target.value)}
              disabled={!availability || availabilityLoading || loading}
              className="w-full rounded border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="text-sm text-gray-700">
            <span className="mb-1 block font-medium">Date To</span>
            <input
              type="date"
              value={dateTo}
              min={dateFrom || availability?.availableFrom}
              max={availability?.availableTo}
              onChange={(event) => setDateTo(event.target.value)}
              disabled={!availability || availabilityLoading || loading}
              className="w-full rounded border border-gray-300 px-3 py-2"
            />
          </label>
        </div>

        {availabilityLoading && (
          <div className="mb-4 rounded bg-blue-50 p-4 text-sm text-blue-700">
            Loading processed period from OLAP...
          </div>
        )}

        <button
          onClick={downloadReport}
          disabled={loading || availabilityLoading || !availability}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading || availabilityLoading || !availability ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Preparing CDN Link...' : 'Download Report'}
        </button>

        {info && (
          <div className="mt-4 rounded bg-green-100 p-4 text-green-700">
            {info}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded bg-red-100 p-4 text-red-700">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;

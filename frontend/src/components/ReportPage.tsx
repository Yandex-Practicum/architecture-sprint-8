import React, {useState, useEffect, useCallback} from 'react';
import authService, {UserInfo} from '../services/AuthService';

interface ReportInfo {
    url: string;
    cached: boolean;
    cacheStatus: string;
}

const ReportPage: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [user, setUser] = useState<UserInfo | null>(null);
    const [authenticated, setAuthenticated] = useState(false);
    const [checkingAuth, setCheckingAuth] = useState(true);
    const [reportInfo, setReportInfo] = useState<ReportInfo | null>(null);

    const checkAuth = useCallback(async () => {
        try {
            console.log('Checking authentication...');
            const isAuthenticated = await authService.checkAuth();
            console.log('Is authenticated:', isAuthenticated);

            if (isAuthenticated) {
                const userInfo = await authService.getCurrentUser();
                console.log('User info:', userInfo);
                setUser(userInfo);
                setAuthenticated(true);
            } else {
                setAuthenticated(false);
                setUser(null);
            }
        } catch (error) {
            console.error('Check auth error:', error);
            setAuthenticated(false);
            setUser(null);
        } finally {
            setCheckingAuth(false);
        }
    }, []);

    useEffect(() => {
        const urlParams = new URLSearchParams(window.location.search);
        const authSuccess = urlParams.get('auth');
        const authFailed = urlParams.get('auth_failed');
        const errorParam = urlParams.get('error');

        if (authSuccess === 'success') {
            console.log('Auth success! Checking user...');
            window.history.replaceState({}, document.title, window.location.pathname);
            checkAuth();
        } else if (authFailed === 'failed' || errorParam) {
            console.log('Auth failed:', errorParam);
            window.history.replaceState({}, document.title, window.location.pathname);
            setError(errorParam || 'Authentication failed');
            setCheckingAuth(false);
            setAuthenticated(false);
        } else {
            checkAuth();
        }
    }, [checkAuth]);

    const getReportInfo = async () => {
        if (!authenticated) {
            setError('Please login first');
            return;
        }

        try {
            setLoading(true);
            setError(null);
            setReportInfo(null);

            const response = await authService.getReport();

            if (!response.ok) {
                if (response.status === 401 || response.status === 403) {
                    setAuthenticated(false);
                    setUser(null);
                    authService.login();
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            setReportInfo(data);

            console.log('Report info received:', data);

        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    const handleLogin = () => {
        setCheckingAuth(true);
        authService.login();
    };

    const handleLogout = async () => {
        await authService.logout();
        setAuthenticated(false);
        setUser(null);
        window.location.href = '/';
    };

    if (checkingAuth) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-100">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                    <p className="mt-4 text-gray-600">Checking authentication...</p>
                </div>
            </div>
        );
    }

    if (!authenticated) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
                <div className="p-8 bg-white rounded-lg shadow-md text-center">
                    <h1 className="text-2xl font-bold mb-4">Welcome to BionicPro Reports</h1>
                    <p className="text-gray-600 mb-6">Please login to access usage reports</p>
                    {error && (
                        <div className="mb-4 p-2 bg-red-100 text-red-700 rounded text-sm">
                            {error}
                        </div>
                    )}
                    <button
                        onClick={handleLogin}
                        className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                    >
                        Login with Keycloak
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-100">
            <header className="bg-white shadow-md">
                <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
                    <h1 className="text-xl font-bold text-gray-800">BionicPro Reports</h1>
                    <div className="flex items-center space-x-4">
                        <div className="text-right">
                            <p className="text-sm text-gray-600">{user?.username}</p>
                            <p className="text-xs text-gray-500">{user?.roles?.join(', ')}</p>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
                        >
                            Logout
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 py-8">
                <div className="bg-white rounded-lg shadow-md p-8">
                    <h2 className="text-2xl font-bold mb-6">Usage Reports</h2>

                    <div className="space-y-4">
                        <div className="p-4 bg-blue-50 rounded-lg">
                            <h3 className="font-semibold text-blue-900 mb-2">Get Report Information</h3>
                            <p className="text-sm text-blue-700 mb-4">
                                Get information about your personal usage report
                            </p>
                            <button
                                onClick={getReportInfo}
                                disabled={loading}
                                className={`px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors ${
                                    loading ? 'opacity-50 cursor-not-allowed' : ''
                                }`}
                            >
                                {loading ? (
                                    <span className="flex items-center">
                                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                                             xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor"
                                                    strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor"
                                                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        Loading...
                                    </span>
                                ) : (
                                    'Get Report Info'
                                )}
                            </button>
                        </div>

                        {reportInfo && (
                            <div className="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
                                <h3 className="font-semibold text-green-800 mb-3">Report Information</h3>
                                <div className="space-y-2 text-sm">
                                    <div className="flex">
                                        <span className="font-medium w-32 text-gray-600">URL:</span>
                                        <span className="text-gray-800 break-all">{reportInfo.url}</span>
                                    </div>
                                    <div className="flex">
                                        <span className="font-medium w-32 text-gray-600">Cached:</span>
                                        <span className={`${reportInfo.cached ? 'text-green-600' : 'text-yellow-600'}`}>
                                            {reportInfo.cached ? 'Yes (HIT)' : 'No (MISS)'}
                                        </span>
                                    </div>
                                    <div className="flex">
                                        <span className="font-medium w-32 text-gray-600">Cache Status:</span>
                                        <span className="text-gray-800">{reportInfo.cacheStatus || 'N/A'}</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {error && (
                            <div className="p-4 bg-red-100 text-red-700 rounded-lg">
                                <strong>Error:</strong> {error}
                            </div>
                        )}
                    </div>
                </div>
            </main>

        </div>
    );
};

export default ReportPage;
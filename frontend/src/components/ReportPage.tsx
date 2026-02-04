import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

const ReportPage: React.FC = () => {
    const { keycloak, initialized } = useKeycloak();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [report, setReport] = useState<any>(null);

    const downloadReport = async () => {
        if (!keycloak?.token) {
            setError('Not authenticated');
            return;
        }

        try {
            setLoading(true);
            setError(null);

            const response = await fetch(
                `${process.env.REACT_APP_API_URL}/reports`,
                {
                    method: 'GET',
                    headers: {
                        Authorization: `Bearer ${keycloak.token}`,
                    },
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            setReport(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    if (!initialized) {
        return <div>Loading Keycloak…</div>;
    }

    if (!keycloak.authenticated) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
                <button
                    onClick={() =>
                        keycloak.login({
                            redirectUri: 'http://localhost:3000',
                        })
                    }
                    className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                    Login
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
            <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-2xl">
                <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

                <button
                    onClick={downloadReport}
                    disabled={loading}
                    className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
                        loading ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                >
                    {loading ? 'Generating Report…' : 'Download Report'}
                </button>

                {error && (
                    <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
                        {error}
                    </div>
                )}

                {report && (
                    <pre className="mt-4 p-4 bg-gray-100 rounded text-left overflow-auto">
            {JSON.stringify(report, null, 2)}
          </pre>
                )}
            </div>
        </div>
    );
};

export default ReportPage;

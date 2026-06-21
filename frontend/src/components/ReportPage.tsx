import React, {useState} from 'react';
import {useKeycloak} from '@react-keycloak/web';

type ProstheticReportResponse = {
    userId: string;
    prostheticId: string;
    reportDate: string;

    userFullName: string;
    prostheticModel: string;
    serialNumber: string;

    totalEvents: number;
    avgResponseTimeMs: number;
    maxResponseTimeMs: number;
    avgSensorNoise: number;
    lowBatteryEvents: number;

    lastTelemetryAt: string;
    updatedAt: string;
};

const ReportPage: React.FC = () => {
    const {keycloak, initialized} = useKeycloak();
    const today = new Date().toISOString().slice(0, 10);

    const [reports, setReports] = useState<ProstheticReportResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [from, setFrom] = useState(today);
    const [to, setTo] = useState(today);

    const loadReport = async () => {
        if (!keycloak?.authenticated || !keycloak.token) {
            setError('Пользователь не авторизован');
            return;
        }

        if (!from || !to) {
            setError('Выберите период отчёта');
            return;
        }

        if (from > to) {
            setError('Дата начала периода не может быть позже даты окончания');
            return;
        }

        try {
            setLoading(true);
            setError(null);

            await keycloak.updateToken(30);

            const response = await fetch(`${process.env.REACT_APP_API_URL}/reports?from=${from}&to=${to}`, {
                method: 'GET',
                headers: {
                    Authorization: `Bearer ${keycloak.token}`,
                    Accept: 'application/json',
                },
            });
            if (!response.ok) {
                throw new Error(`Ошибка получения отчёта: ${response.status}`);
            }

            const data: ProstheticReportResponse[] = await response.json();
            setReports(data);
        } catch (err) {
            setReports([]);
            setError(err instanceof Error ? err.message : 'Произошла неизвестная ошибка');
        } finally {
            setLoading(false);
        }
    };

    const logout = () => {
        keycloak.logout({
            redirectUri: window.location.origin,
        });
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
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
            <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-6xl">
                <h1 className="text-2xl font-bold mb-2">Usage Reports</h1>

                <p className="mb-6 text-gray-600">
                    Пользователь: <b>{keycloak.tokenParsed?.preferred_username}</b>
                </p>

                <div className="flex gap-4 mb-4">
                    <label className="flex flex-col">
                        <span className="mb-1 text-sm text-gray-600">Дата с</span>
                        <input
                            type="date"
                            value={from}
                            onChange={(e) => setFrom(e.target.value)}
                            className="border rounded px-3 py-2"
                        />
                    </label>

                    <label className="flex flex-col">
                        <span className="mb-1 text-sm text-gray-600">Дата по</span>
                        <input
                            type="date"
                            value={to}
                            onChange={(e) => setTo(e.target.value)}
                            className="border rounded px-3 py-2"
                        />
                    </label>
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={loadReport}
                        disabled={loading}
                        className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
                            loading ? 'opacity-50 cursor-not-allowed' : ''
                        }`}
                    >
                        {loading ? 'Loading report...' : 'Get report'}
                    </button>

                    <button
                        onClick={logout}
                        className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
                    >
                        Logout
                    </button>
                </div>

                {error && (
                    <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
                        {error}
                    </div>
                )}

                {!loading && !error && reports.length === 0 && (
                    <div className="mt-4 text-gray-600">
                        Отчёты за выбранный период не найдены.
                    </div>
                )}

                {reports.length > 0 && (
                    <div className="mt-6 overflow-x-auto">
                        <table className="min-w-full border border-gray-300 text-sm">
                            <thead>
                            <tr className="bg-gray-100">
                                <th className="border px-3 py-2">Дата</th>
                                <th className="border px-3 py-2">Протез</th>
                                <th className="border px-3 py-2">Модель</th>
                                <th className="border px-3 py-2">Серийный номер</th>
                                <th className="border px-3 py-2">Событий</th>
                                <th className="border px-3 py-2">Среднее время реакции, мс</th>
                                <th className="border px-3 py-2">Макс. время реакции, мс</th>
                                <th className="border px-3 py-2">Средний шум датчиков</th>
                                <th className="border px-3 py-2">Низкая батарея</th>
                            </tr>
                            </thead>
                            <tbody>
                            {reports.map((report) => (
                                <tr key={`${report.prostheticId}-${report.reportDate}`}>
                                    <td className="border px-3 py-2">{report.reportDate}</td>
                                    <td className="border px-3 py-2">{report.prostheticId}</td>
                                    <td className="border px-3 py-2">{report.prostheticModel}</td>
                                    <td className="border px-3 py-2">{report.serialNumber}</td>
                                    <td className="border px-3 py-2">{report.totalEvents}</td>
                                    <td className="border px-3 py-2">{report.avgResponseTimeMs.toFixed(2)}</td>
                                    <td className="border px-3 py-2">{report.maxResponseTimeMs.toFixed(2)}</td>
                                    <td className="border px-3 py-2">{report.avgSensorNoise.toFixed(3)}</td>
                                    <td className="border px-3 py-2">{report.lowBatteryEvents}</td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ReportPage;

import React, { useState } from 'react';

/**
 * BionicPRO — Report Page
 *
 * Поток запроса:
 *   1. Пользователь нажимает «Получить отчёт»
 *   2. Frontend → GET /api/reports/me (cookie: BIONIC_SESSION)
 *   3. BFF проверяет сессию, добавляет Bearer token, проксирует на Report Service
 *   4. Report Service → ClickHouse (витрина user_reports)
 *   5. Ответ отображается в UI
 */

interface ProsthesisReport {
    prosthesisType: string;
    totalSignals: number;
    avgAmplitude: number;
    avgFrequency: number;
    avgDuration: number;
    minSignalTime: string;
    maxSignalTime: string;
}

interface UserReport {
    userId: number;
    customerName: string;
    customerEmail: string;
    reportUpdated: string;
    prostheses: ProsthesisReport[];
}

type PageState = 'idle' | 'loading' | 'success' | 'error' | 'not-found' | 'unauthenticated';

const ReportPage: React.FC = () => {
    const [state, setState] = useState<PageState>('idle');
    const [report, setReport] = useState<UserReport | null>(null);
    const [errorMessage, setErrorMessage] = useState('');

    const fetchReport = async () => {
        setState('loading');
        setReport(null);
        setErrorMessage('');

        try {
            const response = await fetch('/api/reports/me', {
                credentials: 'include',
            });

            if (response.ok) {
                const data: UserReport = await response.json();
                setReport(data);
                setState('success');
            } else if (response.status === 401) {
                setState('unauthenticated');
            } else if (response.status === 404) {
                setState('not-found');
            } else {
                const body = await response.json().catch(() => ({}));
                setErrorMessage(body.error || `Ошибка сервера (${response.status})`);
                setState('error');
            }
        } catch (err) {
            setErrorMessage('Не удалось подключиться к серверу');
            setState('error');
        }
    };

    const handleLogin = () => {
        window.location.href = '/auth/login';
    };

    const handleLogout = async () => {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/auth/logout';
        document.body.appendChild(form);
        form.submit();
    };

    return (
        <div className="min-h-screen bg-gray-50 py-8 px-4">
            <div className="max-w-3xl mx-auto">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                    BionicPRO
                </h1>
                <p className="text-gray-600 mb-8">
                    Отчёт о работе протеза
                </p>

                {/* ── Actions ────────────────────────────────── */}
                <div className="flex gap-3 mb-8">
                    <button
                        onClick={fetchReport}
                        disabled={state === 'loading'}
                        className="bg-blue-600 text-white px-6 py-2 rounded-lg
                                   hover:bg-blue-700 disabled:opacity-50
                                   disabled:cursor-not-allowed transition"
                    >
                        {state === 'loading' ? 'Загрузка...' : 'Получить отчёт'}
                    </button>
                    <button
                        onClick={handleLogout}
                        className="bg-gray-200 text-gray-700 px-4 py-2 rounded-lg
                                   hover:bg-gray-300 transition"
                    >
                        Выйти
                    </button>
                </div>

                {/* ── Unauthenticated ────────────────────────── */}
                {state === 'unauthenticated' && (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                        <p className="text-yellow-800 mb-3">
                            Для просмотра отчёта необходимо войти в систему.
                        </p>
                        <button
                            onClick={handleLogin}
                            className="bg-yellow-600 text-white px-4 py-2 rounded-lg
                                       hover:bg-yellow-700 transition"
                        >
                            Войти
                        </button>
                    </div>
                )}

                {/* ── Not Found ──────────────────────────────── */}
                {state === 'not-found' && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                        <p className="text-blue-800">
                            Отчёт пока недоступен. Данные обновляются раз в сутки
                            в ночное время. Попробуйте позже.
                        </p>
                    </div>
                )}

                {/* ── Error ──────────────────────────────────── */}
                {state === 'error' && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                        <p className="text-red-800">
                            {errorMessage}
                        </p>
                    </div>
                )}

                {/* ── Report ─────────────────────────────────── */}
                {state === 'success' && report && (
                    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
                        {/* Header */}
                        <div className="p-6 border-b border-gray-100">
                            <h2 className="text-xl font-semibold text-gray-900">
                                {report.customerName}
                            </h2>
                            <p className="text-gray-500 text-sm mt-1">
                                {report.customerEmail}
                            </p>
                            <p className="text-gray-400 text-xs mt-2">
                                Обновлено: {report.reportUpdated}
                            </p>
                        </div>

                        {/* Prostheses */}
                        {report.prostheses.map((p, idx) => (
                            <div
                                key={idx}
                                className={`p-6 ${idx < report.prostheses.length - 1 ? 'border-b border-gray-100' : ''}`}
                            >
                                <h3 className="text-lg font-medium text-gray-800 mb-4">
                                    Протез: {p.prosthesisType}
                                </h3>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <Stat label="Сигналов" value={p.totalSignals.toLocaleString()} />
                                    <Stat label="Ср. амплитуда" value={p.avgAmplitude.toFixed(2)} />
                                    <Stat label="Ср. частота" value={`${p.avgFrequency} Гц`} />
                                    <Stat label="Ср. длительность" value={`${p.avgDuration} мс`} />
                                </div>
                                <p className="text-gray-400 text-xs mt-4">
                                    Период: {p.minSignalTime} — {p.maxSignalTime}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

const Stat: React.FC<{ label: string; value: string }> = ({ label, value }) => (
    <div className="bg-gray-50 rounded-lg p-3">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-lg font-semibold text-gray-900">{value}</p>
    </div>
);

export default ReportPage;

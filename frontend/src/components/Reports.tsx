// src/components/ReportViewer.tsx
import React, { useState } from 'react';
import { reportsApi, ReportResponse, ReportData } from '../services/reportsApi';

const ReportViewer: React.FC = () => {
  // Состояния для двух способов
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Данные отчета
  const [reportResponse, setReportResponse] = useState<ReportResponse | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  
  // Фильтры для второго способа
  const [dateFrom, setDateFrom] = useState<string>(() => {
    const date = new Date();
    date.setDate(date.getDate() - 30);
    return date.toISOString().split('T')[0];
  });
  const [dateTo, setDateTo] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  
  const [expandedProsthesis, setExpandedProsthesis] = useState<string | null>(null);

  const loadReportWithoutFilters = async () => {
    setLoading(true);
    setError(null);
    setReportData(null);
    setReportResponse(null);
    
    try {
      const data = await reportsApi.getMyReport();
      setReportData(data);
      
    } catch (err: any) {
      console.error('Failed to load report:', err);
      setError(err.response?.data?.error || err.message || 'Ошибка загрузки отчета');
    } finally {
      setLoading(false);
    }
  };

  // Способ 2: С фильтрами по дате (api/minio/my)
  const loadReportWithFilters = async () => {
    if (!dateFrom || !dateTo) {
      setError('Выберите обе даты');
      return;
    }
    
    setLoading(true);
    setError(null);
    setReportData(null);
    setReportResponse(null);
    
    try {
      const response = await reportsApi.getMinioReport(dateFrom, dateTo);
      setReportResponse(response);
      
      const data = await reportsApi.fetchReportData(response.cdnUrl);
      setReportData(data);
      
      console.log(`Filtered report loaded from ${response.fromCache ? 'cache' : 'fresh generation'}`);
    } catch (err: any) {
      console.error('Failed to load filtered report:', err);
      setError(err.response?.data?.error || err.message || 'Ошибка загрузки отчета с фильтрами');
    } finally {
      setLoading(false);
    }
  };

  // Форматирование даты
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatReactionTime = (ms: number) => `${ms.toFixed(0)} мс`;
  const formatSuccessRate = (rate: number) => `${(rate * 100).toFixed(1)}%`;
  
  const getRateColor = (rate: number) => {
    if (rate >= 0.8) return '#28a745';
    if (rate >= 0.6) return '#ffc107';
    return '#dc3545';
  };

  const getReactionColor = (ms: number) => {
    if (ms <= 80) return '#28a745';
    if (ms <= 120) return '#ffc107';
    return '#dc3545';
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '40px auto', padding: '20px' }}>
      <h1 style={{ marginBottom: '24px', color: '#333' }}>📊 Отчеты по протезам</h1>
      
      {/* Две кнопки для разных способов */}
      <div style={{ display: 'flex', gap: '20px', marginBottom: '32px', flexWrap: 'wrap' }}>
        {/* Способ 1: Без фильтров */}
        <button
          onClick={loadReportWithoutFilters}
          disabled={loading}
          style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            border: 'none',
            padding: '12px 24px',
            borderRadius: '10px',
            fontSize: '14px',
            fontWeight: '600',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1
          }}
        >
          📊 Отчет без фильтров
        </button>

        {/* Способ 2: С фильтрами по дате */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', background: '#f8f9fa', padding: '8px 16px', borderRadius: '12px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#666', marginBottom: '4px' }}>Дата от</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              style={{ padding: '8px', borderRadius: '6px', border: '1px solid #ddd' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#666', marginBottom: '4px' }}>Дата до</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              style={{ padding: '8px', borderRadius: '6px', border: '1px solid #ddd' }}
            />
          </div>
          <button
            onClick={loadReportWithFilters}
            disabled={loading}
            style={{
              background: 'linear-gradient(135deg, #28a745 0%, #20c997 100%)',
              color: 'white',
              border: 'none',
              padding: '8px 20px',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            🔍 Отчет с фильтром
          </button>
        </div>
      </div>

      {/* Индикатор загрузки */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '60px' }}>
          <div style={{
            width: '50px',
            height: '50px',
            border: '4px solid #f3f3f3',
            borderTop: '4px solid #667eea',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 20px'
          }} />
          <p>Генерация отчета...</p>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {/* Ошибка */}
      {error && !loading && (
        <div style={{
          background: '#fee',
          color: '#c33',
          padding: '20px',
          borderRadius: '12px',
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          <p>⚠️ {error}</p>
        </div>
      )}

      {/* Информация о кеше */}
      {reportResponse && reportData && !loading && (
        <div style={{
          background: reportResponse.fromCache ? '#e8f5e9' : '#fff3e0',
          padding: '12px 20px',
          borderRadius: '10px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div style={{ fontSize: '13px' }}>
            {reportResponse.fromCache ? (
              <>✅ Отчет загружен из CDN кеша (действителен до {new Date(reportResponse.cachedUntil).toLocaleDateString()})</>
            ) : (
              <>🔄 Отчет сгенерирован свежий и сохранен в кеш</>
            )}
          </div>
        </div>
      )}

      {/* Отображение данных отчета */}
      {reportData && !loading && (
        <div>
          {/* Информация о пользователе */}
          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '24px',
            marginBottom: '24px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ margin: '0 0 8px 0', color: '#333' }}>
              📊 Отчет по протезам
            </h2>
            <div style={{ color: '#666', marginBottom: '16px' }}>
              Сгенерирован: {formatDateTime(reportData.generatedAt)}
            </div>
            <div style={{
              display: 'flex',
              gap: '24px',
              flexWrap: 'wrap',
              paddingTop: '16px',
              borderTop: '1px solid #f0f0f0'
            }}>
              <div>
                <span style={{ color: '#999', fontSize: '12px' }}>Пользователь</span>
                <div style={{ fontWeight: '500' }}>{reportData.userName || reportData.userId.substring(0, 8)}</div>
              </div>
              <div>
                <span style={{ color: '#999', fontSize: '12px' }}>Email</span>
                <div style={{ fontWeight: '500' }}>{reportData.userEmail || '—'}</div>
              </div>
              <div>
                <span style={{ color: '#999', fontSize: '12px' }}>Всего движений</span>
                <div style={{ fontWeight: '500' }}>{reportData.summary.totalMovements}</div>
              </div>
              <div>
                <span style={{ color: '#999', fontSize: '12px' }}>Дней с данными</span>
                <div style={{ fontWeight: '500' }}>{reportData.summary.daysWithData}</div>
              </div>
            </div>
          </div>

          {/* Сводка */}
          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '24px',
            marginBottom: '24px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
          }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#333' }}>📈 Общая статистика</h3>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '20px',
              marginBottom: '20px'
            }}>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f8f9fa', borderRadius: '12px' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: getReactionColor(reportData.summary.overallAvgReactionTime) }}>
                  {formatReactionTime(reportData.summary.overallAvgReactionTime)}
                </div>
                <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>Среднее время реакции</div>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f8f9fa', borderRadius: '12px' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: getRateColor(reportData.summary.overallSuccessRate) }}>
                  {formatSuccessRate(reportData.summary.overallSuccessRate)}
                </div>
                <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>Успешность движений</div>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f8f9fa', borderRadius: '12px' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold' }}>
                  {reportData.summary.totalMovements}
                </div>
                <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>Всего движений</div>
              </div>
            </div>
            
            {/* Рекомендация */}
            <div style={{
              background: '#fff3e0',
              padding: '16px',
              borderRadius: '12px',
              borderLeft: `4px solid ${reportData.summary.overallSuccessRate < 0.7 ? '#ffc107' : '#28a745'}`
            }}>
              <strong>💡 Рекомендация:</strong> {reportData.summary.recommendation}
            </div>
          </div>

          {/* Детальные данные по протезам */}
          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '24px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
          }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#333' }}>🔧 Данные по протезам</h3>
            
            {reportData.reports.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                Нет данных по протезам
              </div>
            ) : (
              <div>
                {reportData.reports.map((item, index) => (
                  <div
                    key={item.prosthesisId}
                    style={{
                      marginBottom: '16px',
                      border: '1px solid #eee',
                      borderRadius: '12px',
                      overflow: 'hidden'
                    }}
                  >
                    <div
                      onClick={() => setExpandedProsthesis(
                        expandedProsthesis === item.prosthesisId ? null : item.prosthesisId
                      )}
                      style={{
                        padding: '16px',
                        background: '#f8f9fa',
                        cursor: 'pointer',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                      }}
                    >
                      <div>
                        <strong>Протез {index + 1}</strong>
                        <span style={{
                          marginLeft: '12px',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontSize: '11px',
                          background: item.qualityOk ? '#e8f5e9' : '#ffebee',
                          color: item.qualityOk ? '#2e7d32' : '#c62828'
                        }}>
                          {item.qualityOk ? '✓ Качество OK' : '⚠️ Требуется внимание'}
                        </span>
                      </div>
                      <div style={{ color: '#667eea' }}>
                        {expandedProsthesis === item.prosthesisId ? '▲' : '▼'}
                      </div>
                    </div>
                    
                    {expandedProsthesis === item.prosthesisId && (
                      <div style={{ padding: '20px' }}>
                        <div style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                          gap: '16px'
                        }}>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Дата отчета</div>
                            <div>{formatDate(item.reportDate)}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Тип протеза</div>
                            <div>{item.prosthesisType}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Среднее время реакции</div>
                            <div style={{ color: getReactionColor(item.avgReactionTimeMs), fontWeight: '500' }}>
                              {formatReactionTime(item.avgReactionTimeMs)}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Мин/Макс время</div>
                            <div>{formatReactionTime(item.minReactionTimeMs)} / {formatReactionTime(item.maxReactionTimeMs)}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Успешные/Всего</div>
                            <div>{item.successfulMovements} / {item.totalSignals}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Ошибка классификации</div>
                            <div style={{ color: item.misclassificationRate > 0.3 ? '#dc3545' : '#28a745' }}>
                              {formatSuccessRate(item.misclassificationRate)}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Уровень заряда</div>
                            <div>{item.avgBatteryLevel}% (мин: {item.minBatteryLevel}%)</div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Калибровок</div>
                            <div>{item.tuningCount}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#999' }}>Последняя калибровка</div>
                            <div>{formatDate(item.lastTuningDate)}</div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Пустое состояние */}
      {!reportData && !loading && !error && (
        <div style={{
          textAlign: 'center',
          padding: '80px',
          background: 'white',
          borderRadius: '16px',
          color: '#999'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <p>Выберите способ загрузки отчета:</p>
          <ul style={{ marginTop: '16px', color: '#666' }}>
            <li>• <strong>Отчет без фильтров</strong> — полный отчет за весь период</li>
            <li>• <strong>Отчет с фильтром</strong> — выберите диапазон дат</li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default ReportViewer;
// src/components/ReportViewer.tsx
import React, { useState } from 'react';
import { reportsApi, ReportData, ReportItem } from '../services/reportsApi';

const ReportViewer: React.FC = () => {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedProsthesis, setExpandedProsthesis] = useState<string | null>(null);

  // Загрузка отчета
  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportsApi.getMyReport();
      console.log('Получен отчет:', data);
      setReport(data);
    } catch (err: any) {
      console.error('Failed to load report:', err);
      setError(err.response?.data?.message || 'Ошибка загрузки отчета');
    } finally {
      setLoading(false);
    }
  };

  // Форматирование даты
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Форматирование времени реакции
  const formatReactionTime = (ms: number) => {
    return `${ms.toFixed(0)} мс`;
  };

  // Процент успешности
  const formatSuccessRate = (rate: number) => {
    return `${(rate * 100).toFixed(1)}%`;
  };

  // Цвет для показателя
  const getRateColor = (rate: number) => {
    if (rate >= 0.8) return '#28a745';
    if (rate >= 0.6) return '#ffc107';
    return '#dc3545';
  };

  // Цвет для времени реакции
  const getReactionColor = (ms: number) => {
    if (ms <= 80) return '#28a745';
    if (ms <= 120) return '#ffc107';
    return '#dc3545';
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '40px auto', padding: '20px' }}>
      {/* Кнопка загрузки */}
      <div style={{ textAlign: 'center', marginBottom: '30px' }}>
        <button
          onClick={loadReport}
          disabled={loading}
          style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            border: 'none',
            padding: '14px 32px',
            borderRadius: '12px',
            fontSize: '16px',
            fontWeight: '600',
            cursor: 'pointer',
            transition: 'transform 0.2s',
            boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)'
          }}
          onMouseEnter={(e) => {
            if (!loading) e.currentTarget.style.transform = 'translateY(-2px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
          }}
        >
          {loading ? 'Загрузка отчета...' : '📊 Загрузить отчет'}
        </button>
      </div>

      {/* Состояние загрузки */}
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
          <p>Загрузка данных отчета...</p>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {/* Ошибка */}
      {error && (
        <div style={{
          background: '#fee',
          color: '#c33',
          padding: '20px',
          borderRadius: '12px',
          textAlign: 'center'
        }}>
          <p>⚠️ {error}</p>
          <button
            onClick={loadReport}
            style={{
              marginTop: '12px',
              padding: '8px 20px',
              background: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer'
            }}
          >
            Повторить
          </button>
        </div>
      )}

      {/* Отображение отчета */}
      {report && !loading && (
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
              Сгенерирован: {formatDate(report.generatedAt)}
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
                <div style={{ fontWeight: '500' }}>{report.userName || report.userId.substring(0, 8)}</div>
              </div>
              <div>
                <span style={{ color: '#999', fontSize: '12px' }}>Email</span>
                <div style={{ fontWeight: '500' }}>{report.userEmail || '—'}</div>
              </div>
              <div>
                <span style={{ color: '#999', fontSize: '12px' }}>Всего движений</span>
                <div style={{ fontWeight: '500' }}>{report.summary.totalMovements}</div>
              </div>
              <div>
                <span style={{ color: '#999', fontSize: '12px' }}>Дней с данными</span>
                <div style={{ fontWeight: '500' }}>{report.summary.daysWithData}</div>
              </div>
            </div>
          </div>

          {/* Сводка (Summary) */}
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
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: getReactionColor(report.summary.overallAvgReactionTime) }}>
                  {formatReactionTime(report.summary.overallAvgReactionTime)}
                </div>
                <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>Среднее время реакции</div>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f8f9fa', borderRadius: '12px' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: getRateColor(report.summary.overallSuccessRate) }}>
                  {formatSuccessRate(report.summary.overallSuccessRate)}
                </div>
                <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>Успешность движений</div>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f8f9fa', borderRadius: '12px' }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold' }}>
                  {report.summary.totalMovements}
                </div>
                <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>Всего движений</div>
              </div>
            </div>
            
            {/* Рекомендация */}
            <div style={{
              background: '#fff3e0',
              padding: '16px',
              borderRadius: '12px',
              borderLeft: `4px solid ${report.summary.overallSuccessRate < 0.7 ? '#ffc107' : '#28a745'}`
            }}>
              <strong>💡 Рекомендация:</strong> {report.summary.recommendation}
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
            
            {report.reports.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                Нет данных по протезам
              </div>
            ) : (
              <div>
                {report.reports.map((item, index) => (
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
                            <div>{new Date(item.reportDate).toLocaleDateString()}</div>
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
                            <div>{new Date(item.lastTuningDate).toLocaleDateString()}</div>
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
      {!report && !loading && !error && (
        <div style={{
          textAlign: 'center',
          padding: '80px',
          background: 'white',
          borderRadius: '16px',
          color: '#999'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <p>Нажмите кнопку "Загрузить отчет" для просмотра данных</p>
        </div>
      )}
    </div>
  );
};

export default ReportViewer;
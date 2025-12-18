import React, { useState, useEffect } from 'react';
import { ReportsService, UserReport, UserSummary, DataAvailability } from '../services/ReportsService';

interface ReportsComponentProps {
  userId: number;
  className?: string;
}

export const ReportsComponent: React.FC<ReportsComponentProps> = ({
  userId,
  className = ''
}) => {
  const [reportsService] = useState(() => new ReportsService());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [report, setReport] = useState<UserReport | null>(null);
  const [summary, setSummary] = useState<UserSummary | null>(null);
  const [dataAvailability, setDataAvailability] = useState<DataAvailability | null>(null);
  
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  useEffect(() => {
    const today = new Date();
    const thirtyDaysAgo = reportsService.getDaysAgo(30);
    
    setEndDate(reportsService.formatDate(today));
    setStartDate(reportsService.formatDate(thirtyDaysAgo));
    
    loadInitialData();
  }, [userId]);

  const loadInitialData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [summaryData, availabilityData] = await Promise.all([
        reportsService.getUserSummary(userId),
        reportsService.getDataAvailability()
      ]);

      setSummary(summaryData);
      setDataAvailability(availabilityData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Data loading error');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!startDate || !endDate) {
      setError('Select period for report');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const reportData = await reportsService.getUserReport(userId, startDate, endDate);
      setReport(reportData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Report generation error');
    } finally {
      setLoading(false);
    }
  };


  const getBatteryHealthColor = (health: string) => {
    switch (health) {
      case 'Excellent': return '#16a34a';
      case 'Good': return '#2563eb';
      case 'Low': return '#ca8a04';
      case 'Critical': return '#dc2626';
      default: return '#6b7280';
    }
  };

  const getUsageIntensityColor = (intensity: string) => {
    switch (intensity) {
      case 'Very High': return '#16a34a';
      case 'High': return '#2563eb';
      case 'Medium': return '#ca8a04';
      case 'Low': return '#dc2626';
      default: return '#6b7280';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ backgroundColor: 'white', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', borderRadius: '8px', padding: '24px' }}>
        <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937', marginBottom: '16px' }}>
          Prosthesis Work Reports
        </h2>
        
        {error && (
          <div style={{ marginBottom: '16px', padding: '16px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px' }}>
            <div style={{ fontSize: '14px', color: '#dc2626' }}>{error}</div>
          </div>
        )}

        {dataAvailability && (
          <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '6px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#1e40af', marginBottom: '8px' }}>Data Availability</h3>
            <div style={{ fontSize: '14px', color: '#1d4ed8' }}>
              <p>Reports available: {dataAvailability.reports_available ? 'Yes' : 'No'}</p>
              <p>Latest report date: {dataAvailability.latest_report_date || 'No data'}</p>
              <p>Total reports: {dataAvailability.total_reports}</p>
              <p>Telemetry available: {dataAvailability.telemetry_data_available ? 'Yes' : 'No'}</p>
            </div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={dataAvailability?.latest_report_date || undefined}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
            />
          </div>
          
          <div>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              max={dataAvailability?.latest_report_date || undefined}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'end', gap: '8px' }}>
            <button
              onClick={handleGenerateReport}
              disabled={loading}
              style={{
                flex: 1,
                backgroundColor: loading ? '#9ca3af' : '#2563eb',
                color: 'white',
                fontWeight: '500',
                padding: '8px 16px',
                borderRadius: '6px',
                border: 'none',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
              onMouseOver={(e) => !loading && ((e.target as HTMLElement).style.backgroundColor = '#1d4ed8')}
              onMouseOut={(e) => !loading && ((e.target as HTMLElement).style.backgroundColor = '#2563eb')}
            >
              {loading ? 'Generating...' : 'Generate'}
            </button>
          </div>
        </div>
      </div>

      <div style={{ backgroundColor: 'white', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', borderRadius: '8px', padding: '24px' }}>
        <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '16px' }}>Summary</h3>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div style={{ color: '#6b7280' }}>Loading data...</div>
          </div>
        ) : summary && summary.total_movements !== undefined ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2563eb' }}>{summary.total_movements || 0}</div>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>Total movements</div>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#16a34a' }}>{summary.usage_intensity || 'Unknown'}</div>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>Usage intensity</div>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#7c3aed' }}>{summary.data_quality_score ? (summary.data_quality_score * 100).toFixed(1) : '0'}%</div>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>Data quality</div>
              </div>
            </div>
            <div style={{ marginTop: '16px', fontSize: '14px', color: '#6b7280' }}>
              <p><strong>Username:</strong> {summary.customer_name || 'Unknown'}</p>
              <p><strong>Prosthesis type:</strong> {summary.prosthesis_type || 'Unknown'}</p>
              <p><strong>Last activity:</strong> {summary.last_activity_date || 'Unknown'}</p>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div style={{ color: '#6b7280' }}>Data unavailable</div>
          </div>
        )}
      </div>

      {report && (
        <div style={{ backgroundColor: 'white', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', borderRadius: '8px', padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937' }}>
                Report for period {report.report_period.start_date} — {report.report_period.end_date}
              </h3>
              <p style={{ fontSize: '14px', color: '#6b7280', marginTop: '4px' }}>
                Generated: {new Date(report.generated_at).toLocaleString('en-US')}
              </p>
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <h4 style={{ fontSize: '16px', fontWeight: '500', color: '#1f2937', marginBottom: '12px' }}>Summary Metrics</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div style={{ padding: '12px', backgroundColor: '#eff6ff', borderRadius: '8px' }}>
                <div style={{ fontSize: '18px', fontWeight: '600', color: '#1d4ed8' }}>
                  {report.summary_metrics?.total_movements?.toLocaleString('en-US') || '0'}
                </div>
                <div style={{ fontSize: '12px', color: '#2563eb' }}>Total movements</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: '#f0fdf4', borderRadius: '8px' }}>
                <div style={{ fontSize: '18px', fontWeight: '600', color: '#15803d' }}>
                  {report.summary_metrics?.avg_movement_accuracy ? (report.summary_metrics.avg_movement_accuracy * 100).toFixed(1) : '0'}%
                </div>
                <div style={{ fontSize: '12px', color: '#16a34a' }}>Average accuracy</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: '#fefce8', borderRadius: '8px' }}>
                <div style={{ fontSize: '18px', fontWeight: '600', color: '#ca8a04' }}>
                  {report.summary_metrics?.avg_battery_level?.toFixed(1) || '0'}%
                </div>
                <div style={{ fontSize: '12px', color: '#eab308' }}>Average battery level</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: '#faf5ff', borderRadius: '8px' }}>
                <div style={{ fontSize: '18px', fontWeight: '600', color: getUsageIntensityColor(report.summary_usage?.usage_intensity || 'Low') }}>
                  {report.summary_usage?.usage_intensity || 'Unknown'}
                </div>
                <div style={{ fontSize: '12px', color: '#8b5cf6' }}>Usage intensity</div>
              </div>
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <h4 style={{ fontSize: '16px', fontWeight: '500', color: '#1f2937', marginBottom: '12px' }}>Device Status</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div style={{ padding: '12px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>Prosthesis type</div>
                <div style={{ fontWeight: '500' }}>{report.summary_usage?.prosthesis_type || 'Unknown'}</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>Primary muscle group</div>
                <div style={{ fontWeight: '500' }}>{report.summary_usage?.primary_muscle_group || 'Unknown'}</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>Battery status</div>
                <div style={{ fontWeight: '500', color: getBatteryHealthColor(report.summary_usage?.battery_health || 'Good') }}>
                  {report.summary_usage?.battery_health || 'Unknown'}
                </div>
              </div>
            </div>
          </div>

          {report.insights && report.insights.length > 0 && (
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ fontSize: '16px', fontWeight: '500', color: '#1f2937', marginBottom: '12px' }}>Analytical Insights</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(report.insights || []).map((insight, index) => (
                  <div key={index} style={{ padding: '12px', backgroundColor: '#eff6ff', borderLeft: '4px solid #60a5fa' }}>
                    <p style={{ fontSize: '14px', color: '#1e40af' }}>{insight}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.recommendations && report.recommendations.length > 0 && (
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ fontSize: '16px', fontWeight: '500', color: '#1f2937', marginBottom: '12px' }}>Recommendations</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(report.recommendations || []).map((recommendation, index) => (
                  <div key={index} style={{ padding: '12px', backgroundColor: '#f0fdf4', borderLeft: '4px solid #4ade80' }}>
                    <p style={{ fontSize: '14px', color: '#166534' }}>{recommendation}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.daily_metrics && report.daily_metrics.length > 0 && (
            <div>
              <h4 style={{ fontSize: '16px', fontWeight: '500', color: '#1f2937', marginBottom: '12px' }}>Daily Activity</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ minWidth: '100%', borderCollapse: 'collapse' }}>
                  <thead style={{ backgroundColor: '#f9fafb' }}>
                    <tr>
                      <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Date
                      </th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Movements
                      </th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Accuracy
                      </th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Battery
                      </th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: '12px', fontWeight: '500', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Intensity
                      </th>
                    </tr>
                  </thead>
                  <tbody style={{ backgroundColor: 'white' }}>
                    {(report.daily_metrics || []).slice(-10).map((day, index) => (
                      <tr key={index} style={{ borderTop: '1px solid #e5e7eb' }}>
                        <td style={{ padding: '8px 12px', whiteSpace: 'nowrap', fontSize: '14px', color: '#1f2937' }}>
                          {day.report_date}
                        </td>
                        <td style={{ padding: '8px 12px', whiteSpace: 'nowrap', fontSize: '14px', color: '#1f2937' }}>
                          {day.telemetry?.total_movements?.toLocaleString('en-US') || '0'}
                        </td>
                        <td style={{ padding: '8px 12px', whiteSpace: 'nowrap', fontSize: '14px', color: '#1f2937' }}>
                          {day.telemetry?.avg_movement_accuracy ? (day.telemetry.avg_movement_accuracy * 100).toFixed(1) : '0'}%
                        </td>
                        <td style={{ padding: '8px 12px', whiteSpace: 'nowrap', fontSize: '14px', color: '#1f2937' }}>
                          {day.telemetry?.avg_battery_level?.toFixed(1) || '0'}%
                        </td>
                        <td style={{ padding: '8px 12px', whiteSpace: 'nowrap', fontSize: '14px' }}>
                          <span style={{ color: getUsageIntensityColor(day.usage?.usage_intensity || 'Low') }}>
                            {day.usage?.usage_intensity || 'Unknown'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};


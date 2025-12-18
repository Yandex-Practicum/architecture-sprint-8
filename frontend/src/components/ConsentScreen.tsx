import React, { useState } from 'react';

const ConsentScreen: React.FC = () => {
  const [consents, setConsents] = useState({
    dataProcessing: false,
    analytics: false,
    marketing: false
  });

  const handleConsentChange = (type: keyof typeof consents) => {
    setConsents(prev => ({
      ...prev,
      [type]: !prev[type]
    }));
  };

  const handleSubmit = () => {
    console.log('Consent submitted:', consents);
    window.location.href = '/';
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb', padding: '48px 0' }}>
      <div style={{ maxWidth: '512px', margin: '0 auto', padding: '0 16px' }}>
        <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)', padding: '32px' }}>
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <h1 style={{ fontSize: '30px', fontWeight: 'bold', color: '#1f2937', marginBottom: '16px' }}>
              Data Processing Consent
            </h1>
            <p style={{ color: '#6b7280' }}>
              To continue using the BionicPRO system, you must consent to the processing of personal data
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start' }}>
              <input
                id="dataProcessing"
                type="checkbox"
                checked={consents.dataProcessing}
                onChange={() => handleConsentChange('dataProcessing')}
                style={{ marginTop: '4px', height: '16px', width: '16px', color: '#2563eb' }}
              />
              <label htmlFor="dataProcessing" style={{ marginLeft: '12px', fontSize: '14px', color: '#374151' }}>
                <span style={{ fontWeight: '500' }}>Personal Data Processing</span>
                <p style={{ color: '#6b7280', marginTop: '4px' }}>
                  Consent to process personal data for prosthesis management system operation, 
                  including telemetry data and medical indicators.
                </p>
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start' }}>
              <input
                id="analytics"
                type="checkbox"
                checked={consents.analytics}
                onChange={() => handleConsentChange('analytics')}
                style={{ marginTop: '4px', height: '16px', width: '16px', color: '#2563eb' }}
              />
              <label htmlFor="analytics" style={{ marginLeft: '12px', fontSize: '14px', color: '#374151' }}>
                <span style={{ fontWeight: '500' }}>Analytics and Product Improvement</span>
                <p style={{ color: '#6b7280', marginTop: '4px' }}>
                  Use of anonymized data to improve prosthesis algorithms 
                  and develop new features.
                </p>
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start' }}>
              <input
                id="marketing"
                type="checkbox"
                checked={consents.marketing}
                onChange={() => handleConsentChange('marketing')}
                style={{ marginTop: '4px', height: '16px', width: '16px', color: '#2563eb' }}
              />
              <label htmlFor="marketing" style={{ marginLeft: '12px', fontSize: '14px', color: '#374151' }}>
                <span style={{ fontWeight: '500' }}>Marketing Communications</span>
                <p style={{ color: '#6b7280', marginTop: '4px' }}>
                  Receive information about new products, updates and special offers from BionicPRO.
                </p>
              </label>
            </div>
          </div>

          <div style={{ marginTop: '32px', paddingTop: '24px', borderTop: '1px solid #e5e7eb' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <button
                onClick={handleSubmit}
                disabled={!consents.dataProcessing}
                style={{
                  flex: 1,
                  padding: '12px 24px',
                  borderRadius: '6px',
                  fontWeight: '500',
                  backgroundColor: consents.dataProcessing ? '#2563eb' : '#d1d5db',
                  color: consents.dataProcessing ? 'white' : '#6b7280',
                  cursor: consents.dataProcessing ? 'pointer' : 'not-allowed',
                  border: 'none'
                }}
                onMouseOver={(e) => consents.dataProcessing && ((e.target as HTMLElement).style.backgroundColor = '#1d4ed8')}
                onMouseOut={(e) => consents.dataProcessing && ((e.target as HTMLElement).style.backgroundColor = '#2563eb')}
              >
                Accept and Continue
              </button>
              
              <button
                onClick={() => window.location.href = '/'}
                style={{
                  flex: 1,
                  padding: '12px 24px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontWeight: '500',
                  color: '#374151',
                  backgroundColor: 'white',
                  cursor: 'pointer'
                }}
                onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#f9fafb'}
                onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = 'white'}
              >
                Decline
              </button>
            </div>
            
            <p style={{ fontSize: '12px', color: '#6b7280', textAlign: 'center', marginTop: '16px' }}>
              * Personal data processing consent is required to use the system
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConsentScreen;

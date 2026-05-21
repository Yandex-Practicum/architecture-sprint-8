import React, { useEffect } from 'react';

const BFF_URL = 'http://localhost:8081';

const CallbackPage: React.FC = () => {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code  = params.get('code')  ?? '';
    const state = params.get('state') ?? '';

    if (!code) {
      window.location.href = '/';
      return;
    }

    fetch(`${BFF_URL}/auth/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, state }),
      credentials: 'include',
    })
      .then(res => {
        window.location.href = res.ok ? '/' : '/?error=callback_failed';
      })
      .catch(() => {
        window.location.href = '/?error=callback_failed';
      });
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <p className="text-gray-600">Completing authentication...</p>
    </div>
  );
};

export default CallbackPage;

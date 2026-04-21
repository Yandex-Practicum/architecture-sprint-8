// src/components/Dashboard.tsx
import React from 'react';
import { useAuth } from '../contexts/AuthContext';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  
  const stats = {
    projects: 12,
    users: 156,
    tasks: 342,
  };

  return (
    <div className="dashboard-container">
      <div className="dashboard-card">
        <div className="dashboard-header">
          <h1>Welcome back, {user?.username || 'User'}! 👋</h1>
          <p>Your dashboard overview</p>
        </div>
        
        <div className="stats-grid">
          <div className="stat-card">
            <h3>Total Projects</h3>
            <div className="stat-value">{stats.projects}</div>
          </div>
          <div className="stat-card">
            <h3>Active Users</h3>
            <div className="stat-value">{stats.users}</div>
          </div>
          <div className="stat-card">
            <h3>Tasks Completed</h3>
            <div className="stat-value">{stats.tasks}</div>
          </div>
        </div>
        
        <div className="security-info">
          <h3>🔒 Security Status</h3>
          <ul>
            <li>✅ Authenticated via Keycloak</li>
            <li>✅ Two-Factor Authentication with FreeOTP</li>
            <li>✅ Session cookie (HttpOnly, Secure, SameSite=Lax)</li>
            <li>✅ Authorization Code Flow with PKCE</li>
            <li>✅ Yandex ID integration available</li>
            <li>🔐 OTP validation handled by Keycloak</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
import React from 'react';
import { User } from '../services/auth.service';
import { formatDistanceToNow } from 'date-fns';
import './UserProfile.css';

interface UserProfileProps {
  user: User;
  onRefresh?: () => void;
}

export const UserProfile: React.FC<UserProfileProps> = ({ user, onRefresh }) => {
  const getRelativeTime = (dateString: string) => {
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return 'Unknown';
    }
  };

  return (
    <div className="profile-container">
      <div className="profile-card">
        <div className="profile-header">
          <div className="profile-avatar">
            <span className="avatar-initials">
              {user.username}
            </span>
          </div>
          <h2>Welcome back, {user.username}!</h2>
          <p className="profile-subtitle">Your account information</p>
        </div>

        <div className="profile-info">
          <div className="info-row">
            <span className="info-label">User ID:</span>
            <span className="info-value">{user.userId}</span>
          </div>
          
          <div className="info-row">
            <span className="info-label">Username:</span>
            <span className="info-value">{user.username}</span>
          </div>
          
          <div className="info-row">
            <span className="info-label">Account created:</span>
            <span className="info-value">{getRelativeTime(user.createdAt)}</span>
          </div>
          
          {user.lastActivityAt && (
            <div className="info-row">
              <span className="info-label">Last activity:</span>
              <span className="info-value">{getRelativeTime(user.lastActivityAt)}</span>
            </div>
          )}
        </div>

        <div className="profile-stats">
          <div className="stat-card">
            <div className="stat-value">Active</div>
            <div className="stat-label">Session Status</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">Secure</div>
            <div className="stat-label">Cookie Auth</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">Auto-refresh</div>
            <div className="stat-label">Token Renewal</div>
          </div>
        </div>

        {onRefresh && (
          <button onClick={onRefresh} className="refresh-button">
            Refresh User Data
          </button>
        )}
      </div>
    </div>
  );
};
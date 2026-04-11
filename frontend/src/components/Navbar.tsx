import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import './Navbar.css';

interface NavbarProps {
  onLogout?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onLogout }) => {
  const { user, isAuthenticated, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    if (onLogout) {
      onLogout();
    }
  };

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-brand">
          <span className="brand-icon">🔐</span>
          <span className="brand-name">BionicPro</span>
        </div>

        {isAuthenticated && user && (
          <div className="navbar-menu">
            <div className="user-info">
              <span className="user-name">{user.username}</span>
              <span className="user-badge">Active</span>
            </div>
            <button onClick={handleLogout} className="logout-button">
              <span className="logout-icon">🚪</span>
              Logout
            </button>
          </div>
        )}
      </div>
    </nav>
  );
};
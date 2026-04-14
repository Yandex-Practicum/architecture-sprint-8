// src/components/Navbar.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Navbar: React.FC = () => {
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-brand">
          🔐 BionicPRO
        </Link>
        
        {isAuthenticated && (
          <div className="navbar-menu">
            <Link to="/" className="navbar-link">Dashboard</Link>
            <span style={{ color: '#666', marginRight: '10px' }}>
              👤 {user?.username}
            </span>
            <button onClick={logout} className="logout-btn">
              Logout
            </button>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
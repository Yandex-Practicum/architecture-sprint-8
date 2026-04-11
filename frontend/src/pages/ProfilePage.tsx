import React from 'react';
import { UserProfile } from '../components/UserProfile';
import { useAuth } from '../contexts/AuthContext';

export const ProfilePage: React.FC = () => {
  const { user, refreshUser } = useAuth();

  if (!user) {
    return <div>Loading...</div>;
  }

  return (
    <div className="profile-page">
      <UserProfile user={user} onRefresh={refreshUser} />
    </div>
  );
};
import { useAuth } from '../contexts/AuthContext';

export const useAuthHook = () => {
  const auth = useAuth();
  return auth;
};
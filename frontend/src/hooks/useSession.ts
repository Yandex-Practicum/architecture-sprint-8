import { useEffect, useState } from 'react';
import { authService } from '../services/auth.service';

export const useSession = () => {
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    checkSession();
    
    // Периодическая проверка сессии (каждые 30 секунд)
    const interval = setInterval(checkSession, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const checkSession = async () => {
    try {
      const valid = await authService.validateSession();
      setIsValid(valid);
    } catch (error) {
      setIsValid(false);
    } finally {
      setChecking(false);
    }
  };

  return { isValid, checking, checkSession };
};
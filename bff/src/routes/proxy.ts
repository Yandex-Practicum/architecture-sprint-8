import { Router, Request, Response, NextFunction } from 'express';
import axios, { AxiosError } from 'axios';
import { config } from '../config';

const router = Router();

function requireAuth(req: Request, res: Response, next: NextFunction) {
  if (!req.session.accessToken) {
    return res.status(401).json({ error: 'Not authenticated' });
  }

  const now = Date.now();
  const expiresAt = req.session.expiresAt || 0;
  
  if (now >= expiresAt) {
    return res.status(401).json({ 
      error: 'Token expired',
      message: 'Please refresh your session'
    });
  }

  next();
}

router.get('/reports', requireAuth, async (req: Request, res: Response) => {
  try {
    const accessToken = req.session.accessToken;

    console.log('Proxying /reports request to API with params:', req.query);

    const response = await axios.get(`${config.apiUrl}/reports`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
      params: req.query,
    });

    res.json(response.data);
  } catch (error) {
    console.error('API proxy error:', error);
    
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const status = axiosError.response?.status || 500;
      const data = axiosError.response?.data || { error: 'API request failed' };
      return res.status(status).json(data);
    }
    
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.all('*', requireAuth, async (req: Request, res: Response) => {
  try {
    const accessToken = req.session.accessToken;
    const apiPath = req.path;

    console.log(`Proxying ${req.method} ${apiPath} request to API`);

    const response = await axios({
      method: req.method,
      url: `${config.apiUrl}${apiPath}`,
      headers: {
        ...req.headers,
        Authorization: `Bearer ${accessToken}`,
        host: undefined,
      },
      data: req.body,
      params: req.query,
    });

    res.status(response.status).json(response.data);
  } catch (error) {
    console.error('API proxy error:', error);
    
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const status = axiosError.response?.status || 500;
      const data = axiosError.response?.data || { error: 'API request failed' };
      return res.status(status).json(data);
    }
    
    res.status(500).json({ error: 'Internal server error' });
  }
});

export default router;

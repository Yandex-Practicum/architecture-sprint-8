import cors from 'cors';
import express from 'express';
import morgan from 'morgan';
import { authenticateRequest, assertSelfAccess } from './auth.js';
import { config } from './config.js';
import { getReportRows, normalizeDateRange } from './reportRepository.js';

export function createApp() {
  const app = express();

  app.use(cors({ origin: config.corsOrigin }));
  app.use(express.json());
  app.use(morgan('combined'));

  app.get('/health', (_req, res) => {
    res.json({ status: 'ok' });
  });

  app.get('/reports', authenticateRequest, async (req, res, next) => {
    try {
      const { from, to } = normalizeDateRange(req.query);
      const userId = assertSelfAccess(req.auth.userId, req.query.userId);
      const rows = await getReportRows({ userId, from, to });

      res.json({
        userId,
        from,
        to,
        generatedAt: new Date().toISOString(),
        rows,
      });
    } catch (error) {
      next(error);
    }
  });

  app.use((error, _req, res, _next) => {
    const statusCode = error.statusCode || 500;
    res.status(statusCode).json({
      error: statusCode >= 500 ? 'Internal server error' : error.message,
    });
  });

  return app;
}

import express from 'express';
import cors from 'cors';
import { authMiddleware } from './middleware/auth';
import reportsRouter from './routes/reports';

const app = express();
const PORT = process.env.PORT ?? 4000;

app.use(
  cors({
    origin: process.env.CORS_ORIGIN ?? 'http://localhost:3000',
    credentials: true,
  })
);

app.use(express.json());

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// /reports — все запросы требуют валидного Keycloak JWT
app.use('/reports', authMiddleware, reportsRouter);

app.listen(PORT, () => {
  console.log(`Reports API listening on port ${PORT}`);
});

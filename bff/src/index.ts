import express, { Application } from 'express';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import session from 'express-session';
import { config } from './config';
import authRoutes from './routes/auth';
import proxyRoutes from './routes/proxy';

const app: Application = express();

app.use(express.json());
app.use(cookieParser());
app.use(cors({
  origin: config.frontendUrl,
  credentials: true
}));

app.use(session({
  secret: config.sessionSecret,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: config.nodeEnv === 'production',
    sameSite: 'lax',
    maxAge: 24 * 60 * 60 * 1000
  }
}));

app.use('/auth', authRoutes);
app.use('/api', proxyRoutes);

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

const PORT = config.port || 4000;
app.listen(PORT, () => {
  console.log(`BFF server running on port ${PORT}`);
  console.log(`Environment: ${config.nodeEnv}`);
  console.log(`Keycloak URL: ${config.keycloak.url}`);
  console.log(`Frontend URL: ${config.frontendUrl}`);
});

export default app;

import dotenv from 'dotenv';

dotenv.config();

export const config = {
  port: process.env.PORT || 4000,
  nodeEnv: process.env.NODE_ENV || 'development',
  
  keycloak: {
    url: process.env.KEYCLOAK_URL || 'http://localhost:8080',
    publicUrl: process.env.KEYCLOAK_PUBLIC_URL || process.env.KEYCLOAK_URL || 'http://localhost:8080',
    realm: process.env.KEYCLOAK_REALM || 'reports-realm',
    clientId: process.env.KEYCLOAK_CLIENT_ID || 'bionicpro-bff',
    clientSecret: process.env.KEYCLOAK_CLIENT_SECRET || '',
  },
  
  bffUrl: process.env.BFF_URL || 'http://localhost:4000',
  frontendUrl: process.env.FRONTEND_URL || 'http://localhost:3000',
  apiUrl: process.env.API_URL || 'http://localhost:8000',
  
  sessionSecret: process.env.SESSION_SECRET || 'change-this-secret',
  cookieDomain: process.env.COOKIE_DOMAIN || 'localhost',
};

const requiredVars = [
  'KEYCLOAK_URL',
  'KEYCLOAK_CLIENT_SECRET',
  'SESSION_SECRET'
];

if (config.nodeEnv === 'production') {
  requiredVars.forEach(varName => {
    if (!process.env[varName]) {
      console.warn(`Warning: ${varName} is not set in production environment`);
    }
  });
}

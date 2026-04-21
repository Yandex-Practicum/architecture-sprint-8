export interface User {
  authenticated: boolean;
  username: string;
  email: string;
  otpEnabled?: boolean;
  keycloakUserId?: string;
}

export interface SessionResponse {
  authenticated: boolean;
  username: string;
  email: string;
  otpEnabled?: boolean;
}

export interface LoginUrlResponse {
  url: string;
}

export interface ApiError {
  message: string;
  status?: number;
}
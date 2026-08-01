import { apiRequest } from "./client";

export interface AuthenticatedUser {
  id: string;
  username: string;
  created_at: string;
}

interface AccessTokenResponse {
  access_token: string;
  token_type: "bearer";
}

interface Credentials {
  username: string;
  password: string;
}

export function register(credentials: Credentials): Promise<AuthenticatedUser> {
  return apiRequest<AuthenticatedUser>("/auth/register", {
    method: "POST",
    body: credentials,
  });
}

export function login(credentials: Credentials): Promise<AccessTokenResponse> {
  return apiRequest<AccessTokenResponse>("/auth/login", {
    method: "POST",
    body: credentials,
  });
}

export function getCurrentUser(token: string): Promise<AuthenticatedUser> {
  return apiRequest<AuthenticatedUser>("/auth/me", { token });
}

import { apiFetch } from "./client";
import type { MeResponse, MessageResponse } from "./types";

export const register = (email: string, password: string) =>
  apiFetch<MessageResponse>("/auth/register", {
    method: "POST",
    body: { email, password },
  });

export const verifyEmail = (token: string) =>
  apiFetch<MessageResponse>("/auth/verify-email", {
    method: "POST",
    body: { token },
  });

export const login = (email: string, password: string) =>
  apiFetch<MessageResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
  });

export const logout = () =>
  apiFetch<MessageResponse>("/auth/logout", { method: "POST" });

export const getMe = () => apiFetch<MeResponse>("/auth/me");

export const requestPasswordReset = (email: string) =>
  apiFetch<MessageResponse>("/auth/password-reset/request", {
    method: "POST",
    body: { email },
  });

export const confirmPasswordReset = (token: string, newPassword: string) =>
  apiFetch<MessageResponse>("/auth/password-reset/confirm", {
    method: "POST",
    body: { token, new_password: newPassword },
  });

import { apiFetch } from "./client";
import type { Profile } from "./types";

export const getProfile = () => apiFetch<Profile>("/me/profile");

export const putProfile = (profile: Profile) =>
  apiFetch<Profile>("/me/profile", { method: "PUT", body: profile });

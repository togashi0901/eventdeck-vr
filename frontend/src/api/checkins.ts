import { apiFetch } from "./client";
import type { CheckinItem, CheckinList, MessageResponse } from "./types";

export const createCheckin = (
  eventId: string,
  body: { application_id?: string; short_code?: string; method: "code" | "qr" | "manual" },
) => apiFetch<CheckinItem>(`/events/${eventId}/checkins`, { method: "POST", body });

export const listCheckins = (eventId: string) =>
  apiFetch<CheckinList>(`/events/${eventId}/checkins`);

export const deleteCheckin = (checkinId: string) =>
  apiFetch<MessageResponse>(`/checkins/${checkinId}`, { method: "DELETE" });

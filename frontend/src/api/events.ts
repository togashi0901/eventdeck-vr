import { apiFetch } from "./client";
import type { EventData, EventList, EventUpsert } from "./types";

export const listPublicEvents = (params: {
  q?: string;
  platform?: string;
  page?: number;
}) => {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.platform) query.set("platform", params.platform);
  if (params.page) query.set("page", String(params.page));
  const qs = query.toString();
  return apiFetch<EventList>(`/events${qs ? `?${qs}` : ""}`);
};

export const getEvent = (eventId: string) =>
  apiFetch<EventData>(`/events/${eventId}`);

export const createEvent = (orgId: string, body: EventUpsert) =>
  apiFetch<EventData>(`/orgs/${orgId}/events`, { method: "POST", body });

export const updateEvent = (eventId: string, body: EventUpsert) =>
  apiFetch<EventData>(`/events/${eventId}`, { method: "PUT", body });

export const publishEvent = (eventId: string) =>
  apiFetch<EventData>(`/events/${eventId}/publish`, { method: "POST" });

export const cancelEvent = (eventId: string) =>
  apiFetch<EventData>(`/events/${eventId}/cancel`, { method: "POST" });

export const listOrgEvents = (orgId: string, status?: string) =>
  apiFetch<EventData[]>(
    `/orgs/${orgId}/events${status ? `?status=${status}` : ""}`,
  );

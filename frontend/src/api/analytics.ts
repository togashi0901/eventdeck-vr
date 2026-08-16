import { apiFetch } from "./client";
import type { EventAnalytics, OrgAnalyticsSummary } from "./types";

export const getEventAnalytics = (eventId: string) =>
  apiFetch<EventAnalytics>(`/events/${eventId}/analytics`);

export const getOrgAnalyticsSummary = (orgId: string) =>
  apiFetch<OrgAnalyticsSummary>(`/orgs/${orgId}/analytics/summary`);

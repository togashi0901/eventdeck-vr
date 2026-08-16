import { apiFetch } from "./client";
import type {
  Member,
  MessageResponse,
  Organization,
  PublicOrganization,
} from "./types";

export const createOrganization = (body: {
  name: string;
  slug: string;
  description?: string;
}) => apiFetch<Organization>("/organizations", { method: "POST", body });

export const getPublicOrganization = (slug: string) =>
  apiFetch<PublicOrganization>(`/organizations/${slug}`);

export const getOrganization = (orgId: string) =>
  apiFetch<Organization>(`/orgs/${orgId}`);

export const updateOrganization = (
  orgId: string,
  body: { name: string; description: string | null; website_url: string | null },
) => apiFetch<Organization>(`/orgs/${orgId}`, { method: "PUT", body });

export const listMembers = (orgId: string) =>
  apiFetch<Member[]>(`/orgs/${orgId}/members`);

export const addMember = (
  orgId: string,
  body: { email: string; role: "owner" | "member" },
) => apiFetch<Member>(`/orgs/${orgId}/members`, { method: "POST", body });

export const removeMember = (orgId: string, userId: string) =>
  apiFetch<MessageResponse>(`/orgs/${orgId}/members/${userId}`, {
    method: "DELETE",
  });

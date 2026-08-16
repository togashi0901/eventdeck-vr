import { apiFetch } from "./client";
import type { AnswerIn, ApplicantItem, Application, MyApplication } from "./types";

export const applyToEvent = (eventId: string, answers: AnswerIn[]) =>
  apiFetch<Application>(`/events/${eventId}/applications`, {
    method: "POST",
    body: { answers },
  });

export const listApplicants = (
  eventId: string,
  params: { status?: string; q?: string } = {},
) => {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  const qs = query.toString();
  return apiFetch<ApplicantItem[]>(
    `/events/${eventId}/applications${qs ? `?${qs}` : ""}`,
  );
};

export const cancelApplication = (applicationId: string, reason?: string) =>
  apiFetch<Application>(`/applications/${applicationId}/cancel`, {
    method: "POST",
    body: { reason: reason ?? null },
  });

export const listMyApplications = () =>
  apiFetch<MyApplication[]>("/me/applications");

import { apiFetch } from "./client";
import type { FormItemDraft, FormResponse } from "./types";

export const getForm = (eventId: string) =>
  apiFetch<FormResponse>(`/events/${eventId}/form`);

export const putForm = (eventId: string, items: FormItemDraft[]) =>
  apiFetch<FormResponse>(`/events/${eventId}/form`, {
    method: "PUT",
    body: { items },
  });

import { apiFetch } from "./client";
import type {
  BroadcastRequest,
  NotificationHistory,
  NotificationItem,
} from "./types";

export const broadcastNotification = (eventId: string, body: BroadcastRequest) =>
  apiFetch<{ queued: number }>(`/events/${eventId}/notifications`, {
    method: "POST",
    body,
  });

export const getNotificationHistory = (eventId: string) =>
  apiFetch<NotificationHistory>(`/events/${eventId}/notifications`);

export const listMyNotifications = (unreadOnly = false) =>
  apiFetch<NotificationItem[]>(
    `/me/notifications${unreadOnly ? "?unread_only=true" : ""}`,
  );

export const markNotificationRead = (id: string) =>
  apiFetch<NotificationItem>(`/me/notifications/${id}/read`, { method: "POST" });

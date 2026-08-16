import { apiFetch } from "./client";
import type {
  LotteryExecuteResult,
  LotteryHistoryItem,
  LotteryPreview,
  LotteryRequest,
  LotteryResultItem,
  MessageResponse,
  PageMeta,
} from "./types";

export const previewLottery = (eventId: string, body: LotteryRequest) =>
  apiFetch<LotteryPreview>(`/events/${eventId}/lotteries/preview`, {
    method: "POST",
    body,
  });

export const executeLottery = (eventId: string, body: LotteryRequest) =>
  apiFetch<LotteryExecuteResult>(`/events/${eventId}/lotteries`, {
    method: "POST",
    body,
  });

export const listLotteries = (eventId: string) =>
  apiFetch<LotteryHistoryItem[]>(`/events/${eventId}/lotteries`);

export const getLotteryResults = (lotteryId: string, page = 1) =>
  apiFetch<{ items: LotteryResultItem[]; meta: PageMeta }>(
    `/lotteries/${lotteryId}/results?page=${page}&per_page=100`,
  );

export const promoteApplication = (applicationId: string) =>
  apiFetch<MessageResponse>(`/applications/${applicationId}/promote`, {
    method: "POST",
  });

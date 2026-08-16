// 共通fetchラッパ: X-Requested-With 付与とエラー形式の統一処理 (CLAUDE.md §5)
import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: { field: string; reason: string }[];

  constructor(status: number, body: ApiErrorBody["error"]) {
    super(body.message);
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }
}

export async function apiFetch<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const { method = "GET", body } = options;
  const resp = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let errorBody: ApiErrorBody["error"] = {
      code: "internal_error",
      message: "サーバエラーが発生しました",
    };
    try {
      errorBody = ((await resp.json()) as ApiErrorBody).error;
    } catch {
      // JSONでないエラーレスポンスはそのまま既定メッセージ
    }
    throw new ApiError(resp.status, errorBody);
  }
  return (await resp.json()) as T;
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEvent } from "../api/events";
import {
  executeLottery,
  getLotteryResults,
  listLotteries,
  previewLottery,
  promoteApplication,
} from "../api/lotteries";
import { ApiError } from "../api/client";
import type { LotteryPreview, LotteryRequest, Quota } from "../api/types";
import { ErrorNote, Field, inputClass, SuccessNote } from "../components/Form";
import { formatJst } from "../lib/datetime";
import { AppStatusBadge } from "./MyPage";

const RESULT_LABELS: Record<string, string> = {
  won: "当選",
  waitlisted: "補欠",
  lost: "落選",
};

function buildRequest(waitlistCount: number, firstTimerCount: number): LotteryRequest {
  const quotas: Quota[] = [];
  if (firstTimerCount > 0) {
    quotas.push({
      name: "first_timer",
      label: "初参加者優先枠",
      count: firstTimerCount,
      filter: "first_timer",
    });
  }
  quotas.push({ name: "general", label: "一般枠", count: null, filter: "all" });
  return { quotas, waitlist_count: waitlistCount };
}

export default function LotteryPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const queryClient = useQueryClient();

  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  });
  const historyQuery = useQuery({
    queryKey: ["lotteries", eventId],
    queryFn: () => listLotteries(eventId!),
    enabled: !!eventId,
    retry: false,
  });

  const [waitlistCount, setWaitlistCount] = useState(2);
  const [firstTimerCount, setFirstTimerCount] = useState(0);
  const [preview, setPreview] = useState<LotteryPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [openResults, setOpenResults] = useState<string | null>(null);

  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "操作に失敗しました");

  const previewMutation = useMutation({
    mutationFn: () => previewLottery(eventId!, buildRequest(waitlistCount, firstTimerCount)),
    onSuccess: (data) => {
      setPreview(data);
      setError(null);
    },
    onError,
  });

  const executeMutation = useMutation({
    mutationFn: () => executeLottery(eventId!, buildRequest(waitlistCount, firstTimerCount)),
    onSuccess: (data) => {
      setMessage(
        `第${data.round}回抽選を実行しました: 当選${data.won} / 補欠${data.waitlisted} / 落選${data.lost}`,
      );
      setPreview(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["lotteries", eventId] });
    },
    onError,
  });

  const resultsQuery = useQuery({
    queryKey: ["lottery-results", openResults],
    queryFn: () => getLotteryResults(openResults!),
    enabled: !!openResults,
  });

  const promoteMutation = useMutation({
    mutationFn: promoteApplication,
    onSuccess: () => {
      setMessage("繰り上げました");
      queryClient.invalidateQueries({ queryKey: ["lottery-results"] });
    },
    onError,
  });

  if (eventQuery.isLoading) return <p className="text-slate-500">読み込み中...</p>;
  if (eventQuery.error) return <p className="text-slate-600">イベントが見つかりません。</p>;
  const event = eventQuery.data!;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">抽選: {event.title}</h1>
        <Link to="/dashboard" className="text-sm text-indigo-700 underline">
          ダッシュボードへ戻る
        </Link>
      </div>
      <p className="text-sm text-slate-600">
        定員{event.capacity}名 ・ 応募締切 {formatJst(event.apply_ends_at)}
        (締切後に実行できます)
      </p>
      <ErrorNote message={error} />
      <SuccessNote message={message} />

      <section className="space-y-3 rounded border bg-white p-4">
        <h2 className="font-bold">抽選設定</h2>
        <div className="grid grid-cols-2 gap-3">
          <Field label="補欠数">
            <input
              type="number"
              min={0}
              className={inputClass}
              value={waitlistCount}
              onChange={(e) => setWaitlistCount(Number(e.target.value))}
            />
          </Field>
          <Field label="初参加者優先枠 (0で無効)">
            <input
              type="number"
              min={0}
              className={inputClass}
              value={firstTimerCount}
              onChange={(e) => setFirstTimerCount(Number(e.target.value))}
            />
          </Field>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => previewMutation.mutate()}
            disabled={previewMutation.isPending}
            className="rounded border px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-50"
          >
            プレビュー (実行しない)
          </button>
          {preview && (
            <button
              onClick={() => {
                if (
                  window.confirm(
                    `対象${preview.target_count}名から最大${preview.remaining_capacity}名を当選にします。実行しますか?`,
                  )
                ) {
                  executeMutation.mutate();
                }
              }}
              disabled={executeMutation.isPending}
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              抽選を実行する
            </button>
          )}
        </div>
        {preview && (
          <div className="rounded border border-indigo-200 bg-indigo-50 p-3 text-sm">
            <p>対象応募: {preview.target_count}名</p>
            <p>残定員 (今回の最大当選数): {preview.remaining_capacity}名</p>
            <p>
              枠ごとの合致数:{" "}
              {Object.entries(preview.quota_matches)
                .map(([name, count]) => `${name}=${count}`)
                .join(" / ")}
            </p>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-bold">実行履歴</h2>
        {historyQuery.data?.length === 0 && (
          <p className="text-sm text-slate-500">まだ実行されていません。</p>
        )}
        {historyQuery.data?.map((h) => (
          <div key={h.id} className="rounded border bg-white p-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-bold">第{h.round}回</span>
              <span>
                当選{h.winner_quota} / 補欠{h.waitlist_quota}
              </span>
              <span className="text-slate-500">
                {formatJst(h.executed_at)} ・ 実行者 {h.executed_by_email} ・{" "}
                {h.algorithm_version}
              </span>
              <button
                onClick={() => setOpenResults(openResults === h.id ? null : h.id)}
                className="ml-auto rounded border px-3 py-1 hover:bg-slate-100"
              >
                {openResults === h.id ? "結果を閉じる" : "結果を見る"}
              </button>
            </div>
            {openResults === h.id && resultsQuery.data && (
              <table className="mt-3 w-full text-left text-sm">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1">順位</th>
                    <th>応募者</th>
                    <th>結果</th>
                    <th>枠</th>
                    <th>現在</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {resultsQuery.data.items.map((r) => (
                    <tr key={r.application_id} className="border-t">
                      <td className="py-1">{r.draw_rank}</td>
                      <td>{r.display_name ?? "-"}</td>
                      <td>{RESULT_LABELS[r.result]}</td>
                      <td>{r.quota_name}</td>
                      <td>
                        <AppStatusBadge status={r.current_status} />
                      </td>
                      <td className="text-right">
                        {r.current_status === "waitlisted" && (
                          <button
                            onClick={() => promoteMutation.mutate(r.application_id)}
                            className="rounded border px-2 py-0.5 text-xs hover:bg-slate-100"
                          >
                            手動繰り上げ
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}

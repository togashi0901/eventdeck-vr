import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { createCheckin, deleteCheckin, listCheckins } from "../api/checkins";
import { getEvent } from "../api/events";
import { ApiError } from "../api/client";
import { ErrorNote, inputClass, SuccessNote } from "../components/Form";
import { formatJst } from "../lib/datetime";

export default function CheckinPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const queryClient = useQueryClient();

  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  });
  const listQuery = useQuery({
    queryKey: ["checkins", eventId],
    queryFn: () => listCheckins(eventId!),
    enabled: !!eventId,
    retry: false,
    refetchInterval: 10_000, // 会場運用中の他スタッフの操作を拾う
  });

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["checkins", eventId] });

  const checkinMutation = useMutation({
    mutationFn: () =>
      createCheckin(eventId!, { short_code: code.trim().toLowerCase(), method: "code" }),
    onSuccess: (data) => {
      setMessage(`${data.display_name ?? data.short_code} さんの入場を記録しました`);
      setError(null);
      setCode("");
      refresh();
    },
    onError: (err) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "照合に失敗しました");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCheckin,
    onSuccess: () => {
      setMessage("入場を取り消しました");
      refresh();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "取り消しに失敗しました"),
  });

  if (eventQuery.isLoading) return <p className="text-slate-500">読み込み中...</p>;
  if (eventQuery.error || listQuery.error) {
    return <p className="text-slate-600">入場管理を表示できません(権限がありません)。</p>;
  }
  const stats = listQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">入場管理: {eventQuery.data!.title}</h1>
        <Link to="/dashboard" className="text-sm text-indigo-700 underline">
          ダッシュボードへ戻る
        </Link>
      </div>

      {stats && (
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded border bg-white p-4">
            <p className="text-2xl font-bold">{stats.won_count}</p>
            <p className="text-sm text-slate-500">当選者</p>
          </div>
          <div className="rounded border bg-white p-4">
            <p className="text-2xl font-bold">{stats.checkin_count}</p>
            <p className="text-sm text-slate-500">入場済み</p>
          </div>
          <div className="rounded border bg-white p-4">
            <p className="text-2xl font-bold">{Math.round(stats.checkin_rate * 100)}%</p>
            <p className="text-sm text-slate-500">入場率</p>
          </div>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          checkinMutation.mutate();
        }}
        className="space-y-3 rounded border bg-white p-4"
      >
        <ErrorNote message={error} />
        <SuccessNote message={message} />
        <label className="block text-sm font-medium text-slate-700">
          入場コード (8桁) を入力
        </label>
        <div className="flex gap-2">
          <input
            className={`${inputClass} max-w-xs font-mono tracking-widest`}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            minLength={8}
            maxLength={8}
            placeholder="例: 22284a30"
            required
          />
          <button
            type="submit"
            disabled={checkinMutation.isPending || code.trim().length !== 8}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            照合して入場
          </button>
        </div>
        <p className="text-xs text-slate-500">
          参加者のマイページに表示される短縮コード (QRコードの中身は application_id 全体)
        </p>
      </form>

      <section className="space-y-2">
        <h2 className="font-bold">入場済み一覧</h2>
        {stats?.items.length === 0 && (
          <p className="text-sm text-slate-500">まだ入場者はいません。</p>
        )}
        {stats?.items.map((c) => (
          <div
            key={c.id}
            className="flex flex-wrap items-center gap-3 rounded border bg-white p-3 text-sm"
          >
            <span className="font-bold">{c.display_name ?? "-"}</span>
            {c.vrchat_username && (
              <span className="text-slate-500">@{c.vrchat_username}</span>
            )}
            <code className="rounded bg-slate-100 px-2 py-0.5 font-mono">{c.short_code}</code>
            <span className="text-xs text-slate-500">
              {formatJst(c.checked_in_at)} ・ {c.method} ・ 担当 {c.operator_email ?? "-"}
            </span>
            <button
              onClick={() => {
                if (!window.confirm(`${c.display_name ?? c.short_code} の入場を取り消しますか?`))
                  return;
                deleteMutation.mutate(c.id);
              }}
              className="ml-auto rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
            >
              取り消し
            </button>
          </div>
        ))}
      </section>
    </div>
  );
}

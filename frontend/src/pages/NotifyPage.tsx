import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEvent } from "../api/events";
import {
  broadcastNotification,
  getNotificationHistory,
} from "../api/notifications";
import { ApiError } from "../api/client";
import type { NotificationChannel } from "../api/types";
import {
  ErrorNote,
  Field,
  inputClass,
  SubmitButton,
  SuccessNote,
} from "../components/Form";
import { formatJst } from "../lib/datetime";

const CHANNEL_LABELS: Record<NotificationChannel, string> = {
  in_app: "アプリ内",
  email: "メール",
  push: "プッシュ",
};

export default function NotifyPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const queryClient = useQueryClient();
  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  });
  const historyQuery = useQuery({
    queryKey: ["notification-history", eventId],
    queryFn: () => getNotificationHistory(eventId!),
    enabled: !!eventId,
    retry: false,
  });

  const [type, setType] = useState<"reminder" | "announcement">("announcement");
  const [target, setTarget] = useState<"won" | "all_applicants">("all_applicants");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [channels, setChannels] = useState<NotificationChannel[]>(["in_app", "email"]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const sendMutation = useMutation({
    mutationFn: () =>
      broadcastNotification(eventId!, { type, target, title, body, channels }),
    onSuccess: (data) => {
      setMessage(`${data.queued} 件の通知をキューに登録しました (配信はワーカーが行います)`);
      setTitle("");
      setBody("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["notification-history", eventId] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "配信に失敗しました"),
  });

  const toggleChannel = (ch: NotificationChannel) =>
    setChannels((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch],
    );

  if (eventQuery.isLoading) return <p className="text-slate-500">読み込み中...</p>;
  if (eventQuery.error) return <p className="text-slate-600">イベントが見つかりません。</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">通知配信: {eventQuery.data!.title}</h1>
        <Link to="/dashboard" className="text-sm text-indigo-700 underline">
          ダッシュボードへ戻る
        </Link>
      </div>
      <ErrorNote message={error} />
      <SuccessNote message={message} />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendMutation.mutate();
        }}
        className="space-y-4 rounded border bg-white p-4"
      >
        <div className="grid grid-cols-2 gap-3">
          <Field label="種類">
            <select
              className={inputClass}
              value={type}
              onChange={(e) => setType(e.target.value as typeof type)}
            >
              <option value="announcement">お知らせ</option>
              <option value="reminder">リマインダー</option>
            </select>
          </Field>
          <Field label="宛先">
            <select
              className={inputClass}
              value={target}
              onChange={(e) => setTarget(e.target.value as typeof target)}
            >
              <option value="all_applicants">全応募者 (キャンセル除く)</option>
              <option value="won">当選者のみ</option>
            </select>
          </Field>
        </div>
        <Field label="件名" required>
          <input
            className={inputClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={200}
          />
        </Field>
        <Field label="本文" required>
          <textarea
            className={inputClass}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            required
          />
        </Field>
        <div className="flex gap-4 text-sm">
          {(Object.keys(CHANNEL_LABELS) as NotificationChannel[]).map((ch) => (
            <label key={ch} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={channels.includes(ch)}
                onChange={() => toggleChannel(ch)}
              />
              {CHANNEL_LABELS[ch]}
            </label>
          ))}
        </div>
        <SubmitButton disabled={sendMutation.isPending || channels.length === 0}>
          配信する
        </SubmitButton>
      </form>

      <section className="space-y-3">
        <h2 className="font-bold">配信履歴</h2>
        {historyQuery.data && historyQuery.data.summary.length > 0 && (
          <div className="overflow-x-auto rounded border bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-3 py-2">種類</th>
                  <th className="px-3 py-2">チャネル</th>
                  <th className="px-3 py-2">状態</th>
                  <th className="px-3 py-2">件数</th>
                </tr>
              </thead>
              <tbody>
                {historyQuery.data.summary.map((s, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-3 py-1">{s.type}</td>
                    <td className="px-3 py-1">{s.channel}</td>
                    <td className="px-3 py-1">{s.status}</td>
                    <td className="px-3 py-1">{s.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="space-y-2">
          {historyQuery.data?.items.slice(0, 10).map((n) => (
            <div key={n.id} className="rounded border bg-white p-3 text-sm">
              <span className="font-medium">{n.title}</span>
              <span className="ml-2 text-xs text-slate-500">
                {n.type} / {n.channel} / {n.status} / {formatJst(n.created_at)}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

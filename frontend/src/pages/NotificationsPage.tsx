import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  listMyNotifications,
  markNotificationRead,
} from "../api/notifications";
import { formatJst } from "../lib/datetime";
import { useMe } from "../lib/useMe";

export default function NotificationsPage() {
  const { loggedOut } = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);

  useEffect(() => {
    if (loggedOut) navigate("/login");
  }, [loggedOut, navigate]);

  const query = useQuery({
    queryKey: ["my-notifications", unreadOnly],
    queryFn: () => listMyNotifications(unreadOnly),
  });

  const readMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["my-notifications"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">通知</h1>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
          />
          未読のみ
        </label>
      </div>
      {query.isLoading && <p className="text-slate-500">読み込み中...</p>}
      {query.data?.length === 0 && (
        <p className="text-slate-500">通知はありません。</p>
      )}
      <div className="space-y-2">
        {query.data?.map((n) => (
          <div
            key={n.id}
            className={`rounded border p-4 ${
              n.read_at ? "bg-white" : "border-indigo-300 bg-indigo-50"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">{n.title}</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">
                  {n.body}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {formatJst(n.created_at)}
                  {n.event_id && (
                    <Link
                      to={`/events/${n.event_id}`}
                      className="ml-2 text-indigo-700 underline"
                    >
                      イベントを見る
                    </Link>
                  )}
                </p>
              </div>
              {!n.read_at && (
                <button
                  onClick={() => readMutation.mutate(n.id)}
                  className="shrink-0 rounded border px-3 py-1 text-xs hover:bg-white"
                >
                  既読にする
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

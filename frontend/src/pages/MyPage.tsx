import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { cancelApplication, listMyApplications } from "../api/applications";
import { ApiError } from "../api/client";
import { ErrorNote } from "../components/Form";
import { formatJst } from "../lib/datetime";
import { useMe } from "../lib/useMe";

export const APP_STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  pending: { label: "応募中", cls: "bg-blue-100 text-blue-800" },
  won: { label: "当選", cls: "bg-green-100 text-green-800" },
  lost: { label: "落選", cls: "bg-slate-200 text-slate-600" },
  waitlisted: { label: "補欠", cls: "bg-amber-100 text-amber-800" },
  canceled: { label: "キャンセル済み", cls: "bg-red-100 text-red-700" },
};

export function AppStatusBadge(props: { status: string; promoted?: boolean }) {
  const s = APP_STATUS_LABELS[props.status] ?? { label: props.status, cls: "bg-slate-200" };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.label}
      {props.promoted ? " (繰り上げ)" : ""}
    </span>
  );
}

export default function MyPage() {
  const { loggedOut } = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loggedOut) navigate("/login");
  }, [loggedOut, navigate]);

  const query = useQuery({
    queryKey: ["my-applications"],
    queryFn: listMyApplications,
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelApplication(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["my-applications"] }),
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "キャンセルに失敗しました"),
  });

  if (query.isLoading) return <p className="text-slate-500">読み込み中...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">マイページ — 応募一覧</h1>
      <ErrorNote message={error} />
      {query.data?.length === 0 && (
        <p className="text-slate-500">
          まだ応募がありません。{" "}
          <Link to="/events" className="text-indigo-700 underline">
            公開イベントを見る
          </Link>
        </p>
      )}
      <div className="space-y-3">
        {query.data?.map((a) => (
          <div key={a.id} className="rounded border bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Link
                  to={`/events/${a.event.id}`}
                  className="font-bold text-indigo-700 hover:underline"
                >
                  {a.event.title}
                </Link>
                <AppStatusBadge status={a.status} promoted={a.promoted} />
              </div>
              {(a.status === "pending" || a.status === "won" || a.status === "waitlisted") && (
                <button
                  onClick={() => {
                    if (!window.confirm("応募をキャンセルしますか?")) return;
                    setError(null);
                    cancelMutation.mutate(a.id);
                  }}
                  className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
                >
                  キャンセル
                </button>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-600">
              {formatJst(a.event.starts_at)} 開始 ・ 主催 {a.event.organization_name} ・ 応募日{" "}
              {formatJst(a.applied_at)}
            </p>
            {a.status === "won" && (
              <div className="mt-3 flex items-center gap-4 rounded border border-green-200 bg-green-50 p-3">
                <QRCodeSVG value={a.id} size={96} marginSize={1} />
                <div className="text-sm">
                  <p className="font-medium text-green-900">入場用QRコード</p>
                  <p className="mt-1">
                    短縮コード:{" "}
                    <code className="rounded bg-white px-2 py-0.5 font-mono text-base tracking-widest">
                      {a.short_code}
                    </code>
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    受付でQRを提示するか、短縮コードを伝えてください
                  </p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

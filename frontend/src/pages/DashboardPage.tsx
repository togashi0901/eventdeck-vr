import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { cancelEvent, listOrgEvents, publishEvent } from "../api/events";
import { ApiError } from "../api/client";
import { StatusBadge } from "../components/EventCard";
import { ErrorNote, inputClass } from "../components/Form";
import { formatJst } from "../lib/datetime";
import { useMe } from "../lib/useMe";

export default function DashboardPage() {
  const { me, loggedOut, isLoading } = useMe();
  const navigate = useNavigate();
  const [orgId, setOrgId] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (loggedOut) navigate("/login");
  }, [loggedOut, navigate]);

  useEffect(() => {
    if (me && me.organizations.length > 0 && !orgId) {
      setOrgId(me.organizations[0].id);
    }
  }, [me, orgId]);

  const eventsQuery = useQuery({
    queryKey: ["org-events", orgId, statusFilter],
    queryFn: () => listOrgEvents(orgId, statusFilter || undefined),
    enabled: !!orgId,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["org-events"] });
    queryClient.invalidateQueries({ queryKey: ["events"] });
  };

  const publishMutation = useMutation({
    mutationFn: publishEvent,
    onSuccess: refresh,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "公開に失敗しました"),
  });
  const cancelMutation = useMutation({
    mutationFn: cancelEvent,
    onSuccess: refresh,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "中止に失敗しました"),
  });

  if (isLoading || !me) return <p className="text-slate-500">読み込み中...</p>;

  if (me.organizations.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">ダッシュボード</h1>
        <p className="text-slate-600">まだ団体に所属していません。</p>
        <Link
          to="/organizations/new"
          className="inline-block rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700"
        >
          団体を作成する
        </Link>
      </div>
    );
  }

  const currentOrg = me.organizations.find((o) => o.id === orgId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">ダッシュボード</h1>
        <div className="flex items-center gap-2">
          {me.organizations.length > 1 && (
            <select
              className={inputClass}
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
            >
              {me.organizations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          )}
          <Link
            to={`/orgs/${orgId}/analytics`}
            className="rounded border px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            分析
          </Link>
          <Link
            to={`/orgs/${orgId}/settings`}
            className="rounded border px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            団体設定
          </Link>
          <Link
            to={`/orgs/${orgId}/events/new`}
            className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
          >
            新規イベント
          </Link>
        </div>
      </div>
      <p className="text-sm text-slate-600">
        団体: {currentOrg?.name}({currentOrg?.role}
        )
      </p>
      <ErrorNote message={error} />

      <select
        className={`${inputClass} max-w-40`}
        value={statusFilter}
        onChange={(e) => setStatusFilter(e.target.value)}
      >
        <option value="">全ステータス</option>
        <option value="draft">下書き</option>
        <option value="published">公開中</option>
        <option value="canceled">中止</option>
      </select>

      {eventsQuery.isLoading && <p className="text-slate-500">読み込み中...</p>}
      {eventsQuery.data?.length === 0 && (
        <p className="text-slate-500">イベントがありません。</p>
      )}
      <div className="space-y-3">
        {eventsQuery.data?.map((e) => (
          <div key={e.id} className="rounded border bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Link
                  to={`/events/${e.id}`}
                  className="font-bold text-indigo-700 hover:underline"
                >
                  {e.title}
                </Link>
                <StatusBadge status={e.status} />
              </div>
              <div className="flex gap-2 text-sm">
                {(e.status === "draft" || e.status === "published") && (
                  <>
                    <Link
                      to={`/events/${e.id}/edit`}
                      className="rounded border px-3 py-1 hover:bg-slate-100"
                    >
                      編集
                    </Link>
                    <Link
                      to={`/events/${e.id}/form-builder`}
                      className="rounded border px-3 py-1 hover:bg-slate-100"
                    >
                      設問
                    </Link>
                  </>
                )}
                <Link
                  to={`/events/${e.id}/applicants`}
                  className="rounded border px-3 py-1 hover:bg-slate-100"
                >
                  応募者
                </Link>
                {e.selection_method === "lottery" && e.status !== "draft" && (
                  <Link
                    to={`/events/${e.id}/lottery`}
                    className="rounded border px-3 py-1 hover:bg-slate-100"
                  >
                    抽選
                  </Link>
                )}
                {e.status !== "draft" && (
                  <>
                    <Link
                      to={`/events/${e.id}/notify`}
                      className="rounded border px-3 py-1 hover:bg-slate-100"
                    >
                      通知
                    </Link>
                    <Link
                      to={`/events/${e.id}/checkins`}
                      className="rounded border px-3 py-1 hover:bg-slate-100"
                    >
                      入場
                    </Link>
                    <Link
                      to={`/events/${e.id}/analytics`}
                      className="rounded border px-3 py-1 hover:bg-slate-100"
                    >
                      分析
                    </Link>
                  </>
                )}
                {e.status === "draft" && (
                  <button
                    onClick={() => {
                      setError(null);
                      publishMutation.mutate(e.id);
                    }}
                    className="rounded bg-green-600 px-3 py-1 text-white hover:bg-green-700"
                  >
                    公開する
                  </button>
                )}
                {(e.status === "draft" || e.status === "published") && (
                  <button
                    onClick={() => {
                      if (!window.confirm(`「${e.title}」を中止しますか?`)) return;
                      setError(null);
                      cancelMutation.mutate(e.id);
                    }}
                    className="rounded border border-red-300 px-3 py-1 text-red-700 hover:bg-red-50"
                  >
                    中止
                  </button>
                )}
              </div>
            </div>
            <p className="mt-1 text-sm text-slate-600">
              {formatJst(e.starts_at)} 開始 ・ 定員{e.capacity}名 ・{" "}
              {e.selection_method === "lottery" ? "抽選" : "先着"} ・{" "}
              {e.visibility === "public" ? "公開" : "限定公開"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

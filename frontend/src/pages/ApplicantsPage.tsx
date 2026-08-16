import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listApplicants } from "../api/applications";
import { getEvent } from "../api/events";
import { inputClass } from "../components/Form";
import { formatJst } from "../lib/datetime";
import { AppStatusBadge } from "./MyPage";

export default function ApplicantsPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");

  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  });
  const query = useQuery({
    queryKey: ["applicants", eventId, status, q],
    queryFn: () => listApplicants(eventId!, { status, q }),
    enabled: !!eventId,
    retry: false,
  });

  if (query.error || eventQuery.error) {
    return <p className="text-slate-600">応募者一覧を表示できません(権限がありません)。</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">
          応募者一覧{eventQuery.data ? `: ${eventQuery.data.title}` : ""}
        </h1>
        <Link to="/dashboard" className="text-sm text-indigo-700 underline">
          ダッシュボードへ戻る
        </Link>
      </div>
      <div className="flex flex-wrap gap-2">
        <input
          className={`${inputClass} max-w-xs`}
          placeholder="表示名・VRChat名で検索"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          className={`${inputClass} max-w-40`}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">全ステータス</option>
          <option value="pending">応募中</option>
          <option value="won">当選</option>
          <option value="waitlisted">補欠</option>
          <option value="lost">落選</option>
          <option value="canceled">キャンセル</option>
        </select>
        <span className="self-center text-sm text-slate-500">
          {query.data?.length ?? 0} 件
        </span>
      </div>

      {query.isLoading && <p className="text-slate-500">読み込み中...</p>}
      <div className="space-y-3">
        {query.data?.map((a) => (
          <div key={a.id} className="rounded border bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold">{a.display_name ?? "(表示名なし)"}</span>
              {a.vrchat_username && (
                <span className="text-sm text-slate-500">@{a.vrchat_username}</span>
              )}
              <AppStatusBadge status={a.status} promoted={a.promoted} />
              <span className="ml-auto text-xs text-slate-500">
                応募 {formatJst(a.applied_at)}
              </span>
            </div>
            {a.answers.length > 0 && (
              <dl className="mt-2 grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
                {a.answers.map((ans) => (
                  <div key={ans.form_item_id} className="flex gap-2">
                    <dt className="shrink-0 text-slate-500">{ans.label}:</dt>
                    <dd>{ans.values ? ans.values.join(", ") : ans.value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

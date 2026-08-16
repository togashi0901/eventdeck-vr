import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getEvent } from "../api/events";
import { ApiError } from "../api/client";
import type { EventData } from "../api/types";
import { PLATFORM_LABELS, StatusBadge } from "../components/EventCard";
import { formatJst } from "../lib/datetime";
import { useMe } from "../lib/useMe";
import { AppStatusBadge } from "./MyPage";

function ApplySection(props: { event: EventData; loggedIn: boolean }) {
  const { event: e, loggedIn } = props;
  if (e.status !== "published") return null;

  const now = Date.now();
  const beforeStart = now < new Date(e.apply_starts_at).getTime();
  const afterEnd = now > new Date(e.apply_ends_at).getTime();

  if (!loggedIn) {
    return (
      <p className="text-sm text-slate-600">
        応募には{" "}
        <Link to="/login" className="text-indigo-700 underline">
          ログイン
        </Link>{" "}
        が必要です。
      </p>
    );
  }
  if (e.application_state?.applied) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span>あなたの応募状況:</span>
        <AppStatusBadge status={e.application_state.status ?? ""} />
        <Link to="/my" className="text-indigo-700 underline">
          マイページで確認
        </Link>
      </div>
    );
  }
  if (beforeStart) {
    return <p className="text-sm text-slate-600">応募受付は開始前です。</p>;
  }
  if (afterEnd) {
    return <p className="text-sm text-slate-600">応募は締め切られました。</p>;
  }
  return (
    <Link
      to={`/events/${e.id}/apply`}
      className="inline-block rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
    >
      このイベントに応募する
    </Link>
  );
}

export default function EventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const { me } = useMe();
  const query = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  });

  if (query.isLoading) return <p className="text-slate-500">読み込み中...</p>;
  if (query.error) {
    const notFound =
      query.error instanceof ApiError && query.error.status === 404;
    return (
      <p className="text-slate-600">
        {notFound ? "イベントが見つかりません。" : "読み込みに失敗しました。"}
      </p>
    );
  }
  const e = query.data!;
  const isMember = me?.organizations.some((o) => o.id === e.organization.id);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{e.title}</h1>
        <StatusBadge status={e.status} />
      </div>
      <p className="text-sm text-slate-600">
        主催:{" "}
        <Link to={`/o/${e.organization.slug}`} className="text-indigo-700 underline">
          {e.organization.name}
        </Link>
      </p>

      <div className="rounded border bg-white p-4">
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">開催日時</dt>
            <dd>
              {formatJst(e.starts_at)} 〜 {formatJst(e.ends_at)}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">応募期間</dt>
            <dd>
              {formatJst(e.apply_starts_at)} 〜 {formatJst(e.apply_ends_at)}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">プラットフォーム / 会場</dt>
            <dd>
              {PLATFORM_LABELS[e.platform] ?? e.platform}
              {e.world_name ? ` / ${e.world_name}` : ""}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">定員 / 選考方法</dt>
            <dd>
              {e.capacity}名 / {e.selection_method === "lottery" ? "抽選" : "先着"}
            </dd>
          </div>
        </dl>
      </div>

      {e.description && (
        <div className="whitespace-pre-wrap rounded border bg-white p-4 text-sm">
          {e.description}
        </div>
      )}

      <ApplySection event={e} loggedIn={!!me} />

      {isMember && (
        <div className="flex gap-3 text-sm">
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
            応募フォーム設計
          </Link>
          <Link
            to={`/events/${e.id}/applicants`}
            className="rounded border px-3 py-1 hover:bg-slate-100"
          >
            応募者一覧
          </Link>
        </div>
      )}
    </div>
  );
}

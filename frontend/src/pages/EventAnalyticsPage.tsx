import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getEventAnalytics } from "../api/analytics";
import { getEvent } from "../api/events";
import { APP_STATUS_LABELS } from "./MyPage";

function Stat(props: { value: string; label: string }) {
  return (
    <div className="rounded border bg-white p-4 text-center">
      <p className="text-2xl font-bold">{props.value}</p>
      <p className="text-sm text-slate-500">{props.label}</p>
    </div>
  );
}

export default function EventAnalyticsPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  });
  const query = useQuery({
    queryKey: ["event-analytics", eventId],
    queryFn: () => getEventAnalytics(eventId!),
    enabled: !!eventId,
    retry: false,
  });

  if (query.isLoading || eventQuery.isLoading) {
    return <p className="text-slate-500">読み込み中...</p>;
  }
  if (query.error || eventQuery.error) {
    return <p className="text-slate-600">分析を表示できません(権限がありません)。</p>;
  }
  const a = query.data!;
  const maxDaily = Math.max(1, ...a.daily_applications.map((d) => d.count));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">データ分析: {eventQuery.data!.title}</h1>
        <Link to="/dashboard" className="text-sm text-indigo-700 underline">
          ダッシュボードへ戻る
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat value={String(a.applications_total)} label="総応募数" />
        <Stat value={`${Math.round(a.checkin_rate * 100)}%`} label="参加率 (入場/当選)" />
        <Stat value={`${Math.round(a.first_timer_rate * 100)}%`} label="初参加率" />
      </div>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-3 font-bold">ステータス内訳</h2>
        <div className="flex flex-wrap gap-4 text-sm">
          {Object.entries(a.by_status).map(([status, count]) => (
            <div key={status} className="flex items-center gap-2">
              <span className="text-slate-500">
                {APP_STATUS_LABELS[status]?.label ?? status}:
              </span>
              <span className="font-bold">{count}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-3 font-bold">応募推移 (日別・JST)</h2>
        {a.daily_applications.length === 0 ? (
          <p className="text-sm text-slate-500">応募がありません。</p>
        ) : (
          <div className="space-y-1">
            {a.daily_applications.map((d) => (
              <div key={d.date} className="flex items-center gap-2 text-sm">
                <span className="w-24 shrink-0 text-slate-500">{d.date}</span>
                <div
                  className="h-4 rounded bg-indigo-500"
                  style={{ width: `${(d.count / maxDaily) * 70}%`, minWidth: "0.5rem" }}
                />
                <span className="font-medium">{d.count}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

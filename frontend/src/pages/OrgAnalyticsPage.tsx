import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getOrgAnalyticsSummary } from "../api/analytics";
import { StatusBadge } from "../components/EventCard";
import { formatJst } from "../lib/datetime";

export default function OrgAnalyticsPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const query = useQuery({
    queryKey: ["org-analytics", orgId],
    queryFn: () => getOrgAnalyticsSummary(orgId!),
    enabled: !!orgId,
    retry: false,
  });

  if (query.isLoading) return <p className="text-slate-500">読み込み中...</p>;
  if (query.error) {
    return <p className="text-slate-600">分析を表示できません(権限がありません)。</p>;
  }
  const s = query.data!;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">団体分析サマリ</h1>
        <Link to="/dashboard" className="text-sm text-indigo-700 underline">
          ダッシュボードへ戻る
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded border bg-white p-4">
          <p className="text-2xl font-bold">{s.unique_attendees}</p>
          <p className="text-sm text-slate-500">入場ユニークユーザー</p>
        </div>
        <div className="rounded border bg-white p-4">
          <p className="text-2xl font-bold">{s.repeat_attendees}</p>
          <p className="text-sm text-slate-500">リピーター (2回以上入場)</p>
        </div>
        <div className="rounded border bg-white p-4">
          <p className="text-2xl font-bold">{Math.round(s.repeat_rate * 100)}%</p>
          <p className="text-sm text-slate-500">リピート率</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2">イベント</th>
              <th className="px-3 py-2">開催</th>
              <th className="px-3 py-2">状態</th>
              <th className="px-3 py-2 text-right">応募</th>
              <th className="px-3 py-2 text-right">当選</th>
              <th className="px-3 py-2 text-right">入場</th>
              <th className="px-3 py-2 text-right">参加率</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {s.events.map((e) => (
              <tr key={e.event_id} className="border-t">
                <td className="px-3 py-2 font-medium">{e.title}</td>
                <td className="px-3 py-2 text-slate-500">{formatJst(e.starts_at)}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={e.status} />
                </td>
                <td className="px-3 py-2 text-right">{e.applications_total}</td>
                <td className="px-3 py-2 text-right">{e.won_count}</td>
                <td className="px-3 py-2 text-right">{e.checkin_count}</td>
                <td className="px-3 py-2 text-right">
                  {Math.round(e.checkin_rate * 100)}%
                </td>
                <td className="px-3 py-2 text-right">
                  <Link
                    to={`/events/${e.event_id}/analytics`}
                    className="text-indigo-700 underline"
                  >
                    詳細
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

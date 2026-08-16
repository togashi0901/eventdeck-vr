import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listPublicEvents } from "../api/events";
import EventCard, { PLATFORM_LABELS } from "../components/EventCard";
import { inputClass } from "../components/Form";

export default function EventsPage() {
  const [q, setQ] = useState("");
  const [platform, setPlatform] = useState("");
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["events", { q, platform, page }],
    queryFn: () => listPublicEvents({ q, platform, page }),
  });

  const totalPages = query.data
    ? Math.max(1, Math.ceil(query.data.meta.total / query.data.meta.per_page))
    : 1;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">公開イベント</h1>
      <div className="flex flex-wrap gap-2">
        <input
          className={`${inputClass} max-w-xs`}
          placeholder="タイトルで検索"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
        <select
          className={`${inputClass} max-w-40`}
          value={platform}
          onChange={(e) => {
            setPlatform(e.target.value);
            setPage(1);
          }}
        >
          <option value="">全プラットフォーム</option>
          {Object.entries(PLATFORM_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {query.isLoading && <p className="text-slate-500">読み込み中...</p>}
      {query.data && query.data.items.length === 0 && (
        <p className="text-slate-500">公開中のイベントはありません。</p>
      )}
      <div className="space-y-3">
        {query.data?.items.map((e) => <EventCard key={e.id} event={e} />)}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center gap-3 text-sm">
          <button
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            前へ
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            次へ
          </button>
        </div>
      )}
    </div>
  );
}

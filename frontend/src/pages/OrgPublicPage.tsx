import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getPublicOrganization } from "../api/organizations";
import EventCard from "../components/EventCard";

export default function OrgPublicPage() {
  const { slug } = useParams<{ slug: string }>();
  const query = useQuery({
    queryKey: ["org-public", slug],
    queryFn: () => getPublicOrganization(slug!),
    enabled: !!slug,
    retry: false,
  });

  if (query.isLoading) return <p className="text-slate-500">読み込み中...</p>;
  if (query.error) return <p className="text-slate-600">団体が見つかりません。</p>;
  const org = query.data!;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{org.name}</h1>
      {org.description && (
        <p className="whitespace-pre-wrap text-sm text-slate-600">{org.description}</p>
      )}
      {org.website_url && (
        <a
          href={org.website_url}
          className="text-sm text-indigo-700 underline"
          target="_blank"
          rel="noreferrer"
        >
          {org.website_url}
        </a>
      )}
      <h2 className="pt-2 text-lg font-bold">公開中のイベント</h2>
      {org.events.length === 0 ? (
        <p className="text-slate-500">公開中のイベントはありません。</p>
      ) : (
        <div className="space-y-3">
          {org.events.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </div>
      )}
    </div>
  );
}

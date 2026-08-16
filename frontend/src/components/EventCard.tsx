import { Link } from "react-router-dom";
import type { EventData } from "../api/types";
import { formatJst } from "../lib/datetime";

export const PLATFORM_LABELS: Record<string, string> = {
  vrchat: "VRChat",
  cluster: "cluster",
  resonite: "Resonite",
  real: "リアル会場",
  other: "その他",
};

export const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  draft: { label: "下書き", cls: "bg-slate-200 text-slate-700" },
  published: { label: "公開中", cls: "bg-green-100 text-green-800" },
  closed: { label: "締切済", cls: "bg-amber-100 text-amber-800" },
  finished: { label: "終了", cls: "bg-slate-100 text-slate-500" },
  canceled: { label: "中止", cls: "bg-red-100 text-red-700" },
};

export function StatusBadge(props: { status: string }) {
  const s = STATUS_LABELS[props.status] ?? {
    label: props.status,
    cls: "bg-slate-200",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.label}
    </span>
  );
}

export default function EventCard(props: { event: EventData }) {
  const e = props.event;
  return (
    <Link
      to={`/events/${e.id}`}
      className="block rounded border bg-white p-4 hover:border-indigo-400"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-bold">{e.title}</h3>
        <span className="shrink-0 text-xs text-slate-500">
          {PLATFORM_LABELS[e.platform] ?? e.platform}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        {formatJst(e.starts_at)} 開始 ・ 定員{e.capacity}名 ・{" "}
        {e.selection_method === "lottery" ? "抽選" : "先着"}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        主催: {e.organization.name} ／ 応募締切 {formatJst(e.apply_ends_at)}
      </p>
    </Link>
  );
}

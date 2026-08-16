import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createEvent, getEvent, updateEvent } from "../api/events";
import { ApiError } from "../api/client";
import type { EventUpsert } from "../api/types";
import { PLATFORM_LABELS } from "../components/EventCard";
import { ErrorNote, Field, inputClass, SubmitButton } from "../components/Form";
import { isoToLocalInput, localInputToIso } from "../lib/datetime";

interface FormState {
  title: string;
  description: string;
  platform: string;
  world_name: string;
  world_url: string;
  starts_at: string; // datetime-local 形式
  ends_at: string;
  capacity: string;
  selection_method: string;
  apply_starts_at: string;
  apply_ends_at: string;
  visibility: string;
}

const EMPTY: FormState = {
  title: "",
  description: "",
  platform: "vrchat",
  world_name: "",
  world_url: "",
  starts_at: "",
  ends_at: "",
  capacity: "10",
  selection_method: "lottery",
  apply_starts_at: "",
  apply_ends_at: "",
  visibility: "public",
};

export default function EventFormPage() {
  const { orgId, eventId } = useParams<{ orgId?: string; eventId?: string }>();
  const isEdit = !!eventId;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: isEdit,
    retry: false,
  });

  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const e = eventQuery.data;
    if (!e) return;
    setForm({
      title: e.title,
      description: e.description,
      platform: e.platform,
      world_name: e.world_name ?? "",
      world_url: e.world_url ?? "",
      starts_at: isoToLocalInput(e.starts_at),
      ends_at: isoToLocalInput(e.ends_at),
      capacity: String(e.capacity),
      selection_method: e.selection_method,
      apply_starts_at: isoToLocalInput(e.apply_starts_at),
      apply_ends_at: isoToLocalInput(e.apply_ends_at),
      visibility: e.visibility,
    });
  }, [eventQuery.data]);

  const set = (key: keyof FormState, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body: EventUpsert = {
        title: form.title,
        description: form.description,
        platform: form.platform as EventUpsert["platform"],
        world_name: form.world_name || null,
        world_url: form.world_url || null,
        starts_at: localInputToIso(form.starts_at),
        ends_at: localInputToIso(form.ends_at),
        capacity: Number(form.capacity),
        selection_method: form.selection_method as EventUpsert["selection_method"],
        apply_starts_at: localInputToIso(form.apply_starts_at),
        apply_ends_at: localInputToIso(form.apply_ends_at),
        visibility: form.visibility as EventUpsert["visibility"],
        header_image_url: null,
      };
      const saved = isEdit
        ? await updateEvent(eventId!, body)
        : await createEvent(orgId!, body);
      await queryClient.invalidateQueries({ queryKey: ["org-events"] });
      await queryClient.invalidateQueries({ queryKey: ["event", saved.id] });
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  if (isEdit && eventQuery.isLoading) {
    return <p className="text-slate-500">読み込み中...</p>;
  }
  if (isEdit && eventQuery.error) {
    return <p className="text-slate-600">イベントが見つかりません。</p>;
  }
  const published = eventQuery.data?.status === "published";

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-xl font-bold">
        {isEdit ? "イベント編集" : "イベント作成"}
      </h1>
      {published && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          公開中のイベントです。定員は減らせません。
        </p>
      )}
      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
        <ErrorNote message={error} />
        <Field label="タイトル" required>
          <input
            className={inputClass}
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
            required
            maxLength={100}
          />
        </Field>
        <Field label="説明">
          <textarea
            className={inputClass}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            rows={4}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="プラットフォーム">
            <select
              className={inputClass}
              value={form.platform}
              onChange={(e) => set("platform", e.target.value)}
            >
              {Object.entries(PLATFORM_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="選考方法">
            <select
              className={inputClass}
              value={form.selection_method}
              onChange={(e) => set("selection_method", e.target.value)}
            >
              <option value="lottery">抽選</option>
              <option value="first_come">先着</option>
            </select>
          </Field>
        </div>
        <Field label="ワールド / 会場名">
          <input
            className={inputClass}
            value={form.world_name}
            onChange={(e) => set("world_name", e.target.value)}
            maxLength={100}
          />
        </Field>
        <Field label="ワールドURL・招待リンク">
          <input
            className={inputClass}
            value={form.world_url}
            onChange={(e) => set("world_url", e.target.value)}
            maxLength={500}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="開催開始" required>
            <input
              type="datetime-local"
              className={inputClass}
              value={form.starts_at}
              onChange={(e) => set("starts_at", e.target.value)}
              required
            />
          </Field>
          <Field label="開催終了" required>
            <input
              type="datetime-local"
              className={inputClass}
              value={form.ends_at}
              onChange={(e) => set("ends_at", e.target.value)}
              required
            />
          </Field>
          <Field label="応募開始" required>
            <input
              type="datetime-local"
              className={inputClass}
              value={form.apply_starts_at}
              onChange={(e) => set("apply_starts_at", e.target.value)}
              required
            />
          </Field>
          <Field label="応募締切" required>
            <input
              type="datetime-local"
              className={inputClass}
              value={form.apply_ends_at}
              onChange={(e) => set("apply_ends_at", e.target.value)}
              required
            />
          </Field>
        </div>
        <p className="text-xs text-slate-500">
          応募開始 &lt; 応募締切 ≦ 開催開始 &lt; 開催終了 の順になるよう入力してください
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="定員" required>
            <input
              type="number"
              min={1}
              className={inputClass}
              value={form.capacity}
              onChange={(e) => set("capacity", e.target.value)}
              required
            />
          </Field>
          <Field label="公開範囲">
            <select
              className={inputClass}
              value={form.visibility}
              onChange={(e) => set("visibility", e.target.value)}
            >
              <option value="public">公開 (一覧に表示)</option>
              <option value="unlisted">限定公開 (URLを知る人のみ)</option>
            </select>
          </Field>
        </div>
        <SubmitButton disabled={busy}>
          {isEdit ? "保存する" : "下書きとして作成"}
        </SubmitButton>
      </form>
    </div>
  );
}

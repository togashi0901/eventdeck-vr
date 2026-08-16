import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getForm, putForm } from "../api/forms";
import { ApiError } from "../api/client";
import type { AutofillKey, FormItemDraft, FormItemType } from "../api/types";
import {
  ErrorNote,
  Field,
  inputClass,
  SubmitButton,
  SuccessNote,
} from "../components/Form";

const TYPE_LABELS: Record<FormItemType, string> = {
  text: "1行テキスト",
  textarea: "複数行テキスト",
  select: "プルダウン",
  radio: "ラジオボタン",
  checkbox: "チェックボックス(複数)",
  number: "数値",
};

const AUTOFILL_LABELS: Record<AutofillKey, string> = {
  display_name: "表示名",
  vrchat_username: "VRChatユーザー名",
  platform: "プラットフォーム",
  device_note: "利用機材",
  x_account: "X (Twitter) ID",
  discord_account: "Discordユーザー名",
};

const CHOICE_TYPES: FormItemType[] = ["select", "radio", "checkbox"];

interface DraftRow extends FormItemDraft {
  optionsText: string; // カンマ区切り編集用
}

const emptyRow = (): DraftRow => ({
  label: "",
  help_text: null,
  item_type: "text",
  options: null,
  is_required: false,
  autofill_key: null,
  optionsText: "",
});

export default function FormBuilderPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const queryClient = useQueryClient();
  const formQuery = useQuery({
    queryKey: ["form", eventId],
    queryFn: () => getForm(eventId!),
    enabled: !!eventId,
  });

  const [rows, setRows] = useState<DraftRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (formQuery.data) {
      setRows(
        formQuery.data.items.map((i) => ({
          id: i.id,
          label: i.label,
          help_text: i.help_text,
          item_type: i.item_type,
          options: i.options,
          is_required: i.is_required,
          autofill_key: i.autofill_key,
          optionsText: (i.options ?? []).join(", "),
        })),
      );
    }
  }, [formQuery.data]);

  const update = (idx: number, patch: Partial<DraftRow>) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

  const move = (idx: number, dir: -1 | 1) =>
    setRows((prev) => {
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      const items: FormItemDraft[] = rows.map((r) => ({
        id: r.id,
        label: r.label,
        help_text: r.help_text || null,
        item_type: r.item_type,
        options: CHOICE_TYPES.includes(r.item_type)
          ? r.optionsText.split(",").map((s) => s.trim()).filter(Boolean)
          : null,
        is_required: r.is_required,
        autofill_key: r.autofill_key,
      }));
      await putForm(eventId!, items);
      await queryClient.invalidateQueries({ queryKey: ["form", eventId] });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  if (formQuery.isLoading) return <p className="text-slate-500">読み込み中...</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">応募フォーム設計</h1>
        <Link to="/dashboard" className="text-sm text-indigo-700 underline">
          ダッシュボードへ戻る
        </Link>
      </div>
      <p className="text-sm text-slate-600">
        応募が1件以上あると、既存設問の削除・種類変更・必須化はできません(ラベル修正と追加は可)。
      </p>
      <form onSubmit={save} className="space-y-4">
        <ErrorNote message={error} />
        <SuccessNote message={saved ? "保存しました" : null} />
        {rows.map((row, idx) => (
          <div key={row.id ?? `new-${idx}`} className="space-y-3 rounded border bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">設問 {idx + 1}</span>
              <div className="flex gap-1 text-xs">
                <button type="button" onClick={() => move(idx, -1)} className="rounded border px-2 py-1">
                  ↑
                </button>
                <button type="button" onClick={() => move(idx, 1)} className="rounded border px-2 py-1">
                  ↓
                </button>
                <button
                  type="button"
                  onClick={() => setRows((prev) => prev.filter((_, i) => i !== idx))}
                  className="rounded border border-red-300 px-2 py-1 text-red-700"
                >
                  削除
                </button>
              </div>
            </div>
            <Field label="設問文" required>
              <input
                className={inputClass}
                value={row.label}
                onChange={(e) => update(idx, { label: e.target.value })}
                required
                maxLength={200}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="種類">
                <select
                  className={inputClass}
                  value={row.item_type}
                  onChange={(e) => update(idx, { item_type: e.target.value as FormItemType })}
                >
                  {Object.entries(TYPE_LABELS).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="プロフィール自動入力">
                <select
                  className={inputClass}
                  value={row.autofill_key ?? ""}
                  onChange={(e) =>
                    update(idx, {
                      autofill_key: (e.target.value || null) as AutofillKey | null,
                    })
                  }
                >
                  <option value="">なし</option>
                  {Object.entries(AUTOFILL_LABELS).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {CHOICE_TYPES.includes(row.item_type) && (
              <Field label="選択肢 (カンマ区切り)" required>
                <input
                  className={inputClass}
                  value={row.optionsText}
                  onChange={(e) => update(idx, { optionsText: e.target.value })}
                  placeholder="PCVR, Quest単体, デスクトップ"
                  required
                />
              </Field>
            )}
            <Field label="補足説明">
              <input
                className={inputClass}
                value={row.help_text ?? ""}
                onChange={(e) => update(idx, { help_text: e.target.value || null })}
                maxLength={500}
              />
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={row.is_required}
                onChange={(e) => update(idx, { is_required: e.target.checked })}
              />
              必須にする
            </label>
          </div>
        ))}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => setRows((prev) => [...prev, emptyRow()])}
            className="rounded border px-4 py-2 text-sm hover:bg-slate-100"
          >
            + 設問を追加
          </button>
          <SubmitButton disabled={busy}>フォームを保存</SubmitButton>
        </div>
      </form>
    </div>
  );
}

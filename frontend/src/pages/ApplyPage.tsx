import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { applyToEvent } from "../api/applications";
import { getEvent } from "../api/events";
import { getForm } from "../api/forms";
import { ApiError } from "../api/client";
import type { AnswerIn, FormItem } from "../api/types";
import { ErrorNote, Field, inputClass, SubmitButton } from "../components/Form";
import { useMe } from "../lib/useMe";

export default function ApplyPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const { me, loggedOut } = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  });
  const formQuery = useQuery({
    queryKey: ["form", eventId],
    queryFn: () => getForm(eventId!),
    enabled: !!eventId,
    retry: false,
  });

  const [values, setValues] = useState<Record<string, string>>({});
  const [checks, setChecks] = useState<Record<string, string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loggedOut) navigate("/login");
  }, [loggedOut, navigate]);

  // prefill をサーバから受け取り初期値として適用 (§2.5)
  useEffect(() => {
    const data = formQuery.data;
    if (!data?.prefill) return;
    setValues((prev) => {
      const next = { ...prev };
      for (const item of data.items) {
        const pre = data.prefill![item.id];
        if (pre === undefined || next[item.id] !== undefined) continue;
        if (item.options && !item.options.includes(pre)) continue;
        if (item.item_type !== "checkbox") next[item.id] = pre;
      }
      return next;
    });
  }, [formQuery.data]);

  if (eventQuery.isLoading || formQuery.isLoading) {
    return <p className="text-slate-500">読み込み中...</p>;
  }
  if (eventQuery.error || formQuery.error) {
    return <p className="text-slate-600">イベントが見つかりません。</p>;
  }
  const event = eventQuery.data!;
  const form = formQuery.data!;

  if (me && !me.has_profile) {
    return (
      <div className="mx-auto max-w-md space-y-4">
        <h1 className="text-xl font-bold">応募: {event.title}</h1>
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          応募にはプロフィール登録が必要です。
          <Link to="/profile" className="ml-1 text-indigo-700 underline">
            プロフィールを登録する
          </Link>
        </p>
      </div>
    );
  }

  const toggleCheck = (itemId: string, option: string) =>
    setChecks((prev) => {
      const current = prev[itemId] ?? [];
      return {
        ...prev,
        [itemId]: current.includes(option)
          ? current.filter((o) => o !== option)
          : [...current, option],
      };
    });

  const renderInput = (item: FormItem) => {
    const value = values[item.id] ?? "";
    const setValue = (v: string) => setValues((prev) => ({ ...prev, [item.id]: v }));
    switch (item.item_type) {
      case "textarea":
        return (
          <textarea
            className={inputClass}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={3}
            required={item.is_required}
          />
        );
      case "select":
        return (
          <select
            className={inputClass}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required={item.is_required}
          >
            <option value="">選択してください</option>
            {item.options?.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        );
      case "radio":
        return (
          <div className="space-y-1">
            {item.options?.map((o) => (
              <label key={o} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name={item.id}
                  checked={value === o}
                  onChange={() => setValue(o)}
                  required={item.is_required && !value}
                />
                {o}
              </label>
            ))}
          </div>
        );
      case "checkbox":
        return (
          <div className="space-y-1">
            {item.options?.map((o) => (
              <label key={o} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={(checks[item.id] ?? []).includes(o)}
                  onChange={() => toggleCheck(item.id, o)}
                />
                {o}
              </label>
            ))}
          </div>
        );
      case "number":
        return (
          <input
            type="number"
            className={inputClass}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required={item.is_required}
          />
        );
      default:
        return (
          <input
            className={inputClass}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required={item.is_required}
          />
        );
    }
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const answers: AnswerIn[] = [];
      for (const item of form.items) {
        if (item.item_type === "checkbox") {
          const vs = checks[item.id] ?? [];
          if (vs.length) answers.push({ form_item_id: item.id, values: vs });
        } else {
          const v = (values[item.id] ?? "").trim();
          if (v) answers.push({ form_item_id: item.id, value: v });
        }
      }
      await applyToEvent(eventId!, answers);
      await queryClient.invalidateQueries({ queryKey: ["event", eventId] });
      navigate("/my");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "応募に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-xl font-bold">応募: {event.title}</h1>
      {form.prefill && Object.keys(form.prefill).length > 0 && (
        <p className="rounded border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-800">
          プロフィールから一部の回答を自動入力しました。内容を確認して送信してください。
        </p>
      )}
      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
        <ErrorNote message={error} />
        {form.items.length === 0 && (
          <p className="text-sm text-slate-500">このイベントに設問はありません。</p>
        )}
        {form.items.map((item) => (
          <Field key={item.id} label={item.label} required={item.is_required}>
            {item.help_text && (
              <span className="mb-1 block text-xs text-slate-500">{item.help_text}</span>
            )}
            {renderInput(item)}
          </Field>
        ))}
        <SubmitButton disabled={busy}>応募する</SubmitButton>
      </form>
    </div>
  );
}

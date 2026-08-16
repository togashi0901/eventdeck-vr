import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createOrganization } from "../api/organizations";
import { ApiError } from "../api/client";
import { ErrorNote, Field, inputClass, SubmitButton } from "../components/Form";
import { useInvalidateMe } from "../lib/useMe";

export default function NewOrgPage() {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const invalidateMe = useInvalidateMe();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await createOrganization({ name, slug, description });
      await invalidateMe();
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "作成に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-xl font-bold">団体を作成</h1>
      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
        <ErrorNote message={error} />
        <Field label="団体名" required>
          <input
            className={inputClass}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={100}
          />
        </Field>
        <Field label="スラッグ (公開URL用)" required>
          <input
            className={inputClass}
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            required
            pattern="[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]"
            placeholder="例: team-eventdeck"
          />
          <span className="mt-1 block text-xs text-slate-500">
            小文字英数とハイフン、3〜50文字。公開ページは /o/スラッグ になります
          </span>
        </Field>
        <Field label="紹介文">
          <textarea
            className={inputClass}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
        </Field>
        <SubmitButton disabled={busy}>作成する</SubmitButton>
      </form>
    </div>
  );
}

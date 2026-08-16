import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { confirmPasswordReset } from "../api/auth";
import { ApiError } from "../api/client";
import {
  ErrorNote,
  Field,
  inputClass,
  SubmitButton,
  SuccessNote,
} from "../components/Form";

export default function PasswordResetConfirmPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "再設定に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <div className="mx-auto max-w-sm space-y-4">
        <h1 className="text-xl font-bold">パスワード再設定</h1>
        <ErrorNote message="トークンがありません。メールのリンクを開き直してください。" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm space-y-4">
      <h1 className="text-xl font-bold">新しいパスワードの設定</h1>
      {done ? (
        <>
          <SuccessNote message="パスワードを再設定しました。" />
          <Link to="/login" className="text-indigo-700 underline">
            ログインへ進む
          </Link>
        </>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
          <ErrorNote message={error} />
          <Field label="新しいパスワード" required>
            <input
              type="password"
              className={inputClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
            <span className="mt-1 block text-xs text-slate-500">
              8文字以上、英字と数字を含めてください
            </span>
          </Field>
          <SubmitButton disabled={busy}>再設定する</SubmitButton>
        </form>
      )}
    </div>
  );
}

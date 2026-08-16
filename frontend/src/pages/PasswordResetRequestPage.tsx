import { useState } from "react";
import { requestPasswordReset } from "../api/auth";
import { ApiError } from "../api/client";
import {
  ErrorNote,
  Field,
  inputClass,
  SubmitButton,
  SuccessNote,
} from "../components/Form";

export default function PasswordResetRequestPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestPasswordReset(email);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "送信に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm space-y-4">
      <h1 className="text-xl font-bold">パスワード再設定</h1>
      {done ? (
        <SuccessNote message="登録されている場合、再設定メールを送信しました。メール内のリンクを開いてください。" />
      ) : (
        <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
          <ErrorNote message={error} />
          <Field label="登録済みメールアドレス" required>
            <input
              type="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Field>
          <SubmitButton disabled={busy}>再設定メールを送る</SubmitButton>
        </form>
      )}
    </div>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";
import { register } from "../api/auth";
import { ApiError } from "../api/client";
import {
  ErrorNote,
  Field,
  inputClass,
  SubmitButton,
  SuccessNote,
} from "../components/Form";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登録に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="mx-auto max-w-sm space-y-4">
        <h1 className="text-xl font-bold">新規登録</h1>
        <SuccessNote message="確認メールを送信しました。メール内のリンクを開いて登録を完了してください。" />
        <p className="text-sm text-slate-600">
          開発環境では <a href="http://localhost:8025" className="text-indigo-700 underline">MailHog</a>{" "}
          でメールを確認できます。
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm space-y-4">
      <h1 className="text-xl font-bold">新規登録</h1>
      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
        <ErrorNote message={error} />
        <Field label="メールアドレス" required>
          <input
            type="email"
            className={inputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field label="パスワード" required>
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
        <SubmitButton disabled={busy}>登録する</SubmitButton>
      </form>
      <p className="text-sm text-slate-600">
        登録済みの場合は{" "}
        <Link to="/login" className="text-indigo-700 underline">
          ログイン
        </Link>
      </p>
    </div>
  );
}

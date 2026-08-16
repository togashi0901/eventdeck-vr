import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import { ApiError } from "../api/client";
import { ErrorNote, Field, inputClass, SubmitButton } from "../components/Form";
import { useInvalidateMe } from "../lib/useMe";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const invalidateMe = useInvalidateMe();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      await invalidateMe();
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ログインに失敗しました");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm space-y-4">
      <h1 className="text-xl font-bold">ログイン</h1>
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
          />
        </Field>
        <SubmitButton disabled={busy}>ログイン</SubmitButton>
      </form>
      <p className="text-sm text-slate-600">
        <Link to="/password-reset" className="text-indigo-700 underline">
          パスワードを忘れた場合
        </Link>
        {" ・ "}
        <Link to="/register" className="text-indigo-700 underline">
          新規登録
        </Link>
      </p>
    </div>
  );
}

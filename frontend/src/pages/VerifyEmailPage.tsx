import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../api/auth";
import { ApiError } from "../api/client";
import { ErrorNote, SuccessNote } from "../components/Form";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"pending" | "ok" | "error">("pending");
  const [message, setMessage] = useState<string | null>(null);
  const requested = useRef(false);

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("トークンがありません。メールのリンクを開き直してください。");
      return;
    }
    if (requested.current) return; // StrictMode の二重実行でトークンを消費しない
    requested.current = true;
    verifyEmail(token)
      .then(() => setState("ok"))
      .catch((err) => {
        setState("error");
        setMessage(
          err instanceof ApiError ? err.message : "確認に失敗しました",
        );
      });
  }, [token]);

  return (
    <div className="mx-auto max-w-sm space-y-4">
      <h1 className="text-xl font-bold">メールアドレスの確認</h1>
      {state === "pending" && <p className="text-slate-500">確認中...</p>}
      {state === "ok" && (
        <>
          <SuccessNote message="メールアドレスを確認しました。" />
          <Link to="/login" className="text-indigo-700 underline">
            ログインへ進む
          </Link>
        </>
      )}
      {state === "error" && <ErrorNote message={message} />}
    </div>
  );
}

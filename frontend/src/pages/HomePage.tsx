import { Link } from "react-router-dom";
import { useMe } from "../lib/useMe";

export default function HomePage() {
  const { me, isLoading } = useMe();

  if (isLoading) return <p className="text-slate-500">読み込み中...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">EventDeck VR</h1>
      <p className="text-slate-600">VRイベントの募集・抽選・入場管理をひとつに。</p>
      <p>
        <Link to="/events" className="text-indigo-700 underline">
          公開イベントを見る
        </Link>
      </p>
      {me ? (
        <div className="space-y-2 rounded border bg-white p-4">
          <p>
            <span className="font-medium">{me.email}</span> でログイン中
          </p>
          {!me.has_profile && (
            <p className="text-sm text-amber-700">
              プロフィールが未登録です。応募フォームの自動入力に使われます。{" "}
              <Link to="/profile" className="text-indigo-700 underline">
                プロフィールを登録する
              </Link>
            </p>
          )}
          {me.organizations.length > 0 ? (
            <p className="text-sm text-slate-600">
              所属団体: {me.organizations.map((o) => `${o.name} (${o.role})`).join(", ")}
              {" — "}
              <Link to="/dashboard" className="text-indigo-700 underline">
                ダッシュボードへ
              </Link>
            </p>
          ) : (
            <p className="text-sm text-slate-600">
              イベントを主催するには{" "}
              <Link to="/organizations/new" className="text-indigo-700 underline">
                団体を作成
              </Link>{" "}
              してください。
            </p>
          )}
        </div>
      ) : (
        <p>
          <Link to="/login" className="text-indigo-700 underline">
            ログイン
          </Link>{" "}
          または{" "}
          <Link to="/register" className="text-indigo-700 underline">
            新規登録
          </Link>{" "}
          してください。
        </p>
      )}
    </div>
  );
}

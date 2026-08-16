import { Link, Outlet, useNavigate } from "react-router-dom";
import { logout } from "../api/auth";
import { useInvalidateMe, useMe } from "../lib/useMe";

export default function Layout() {
  const { me } = useMe();
  const invalidateMe = useInvalidateMe();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    await invalidateMe();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-lg font-bold text-indigo-700">
            EventDeck VR
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link to="/events" className="text-indigo-700 hover:underline">
              イベント
            </Link>
            {me ? (
              <>
                {me.organizations.length > 0 && (
                  <Link to="/dashboard" className="text-indigo-700 hover:underline">
                    ダッシュボード
                  </Link>
                )}
                <Link to="/my" className="text-indigo-700 hover:underline">
                  マイページ
                </Link>
                <Link to="/notifications" className="text-indigo-700 hover:underline">
                  通知
                </Link>
                <Link to="/profile" className="text-indigo-700 hover:underline">
                  プロフィール
                </Link>
                <span className="text-slate-500">{me.email}</span>
                <button
                  onClick={onLogout}
                  className="rounded border px-3 py-1 hover:bg-slate-100"
                >
                  ログアウト
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="text-indigo-700 hover:underline">
                  ログイン
                </Link>
                <Link
                  to="/register"
                  className="rounded bg-indigo-600 px-3 py-1 text-white hover:bg-indigo-700"
                >
                  新規登録
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

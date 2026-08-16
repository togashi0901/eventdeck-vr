import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { getProfile, putProfile } from "../api/profile";
import type { Platform, Profile } from "../api/types";
import {
  ErrorNote,
  Field,
  inputClass,
  SubmitButton,
  SuccessNote,
} from "../components/Form";
import { useInvalidateMe, useMe } from "../lib/useMe";

const PLATFORM_OPTIONS: { value: Platform; label: string }[] = [
  { value: "pcvr", label: "PCVR" },
  { value: "desktop", label: "デスクトップ" },
  { value: "quest_standalone", label: "Quest単体" },
  { value: "mobile", label: "モバイル" },
  { value: "unknown", label: "未設定" },
];

const EMPTY: Profile = {
  display_name: "",
  vrchat_username: null,
  platform: "unknown",
  device_note: null,
  x_account: null,
  discord_account: null,
  bio: null,
};

export default function ProfilePage() {
  const { loggedOut, isLoading: meLoading } = useMe();
  const navigate = useNavigate();
  const invalidateMe = useInvalidateMe();

  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: getProfile,
    retry: (count, error) =>
      !(error instanceof ApiError && [401, 404].includes(error.status)) && count < 2,
  });

  const [form, setForm] = useState<Profile>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loggedOut) navigate("/login");
  }, [loggedOut, navigate]);

  useEffect(() => {
    if (profileQuery.data) setForm(profileQuery.data);
  }, [profileQuery.data]);

  if (meLoading || profileQuery.isLoading) {
    return <p className="text-slate-500">読み込み中...</p>;
  }

  const isNew =
    profileQuery.error instanceof ApiError && profileQuery.error.status === 404;

  const set = (key: keyof Profile, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value === "" ? null : value }));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      await putProfile(form);
      await Promise.all([profileQuery.refetch(), invalidateMe()]);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-xl font-bold">
        {isNew ? "プロフィール登録" : "プロフィール編集"}
      </h1>
      <p className="text-sm text-slate-600">
        この内容はイベント応募フォームの自動入力に使われます。
      </p>
      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
        <ErrorNote message={error} />
        <SuccessNote message={saved ? "保存しました" : null} />
        <Field label="表示名" required>
          <input
            className={inputClass}
            value={form.display_name}
            onChange={(e) => set("display_name", e.target.value)}
            required
            maxLength={50}
          />
        </Field>
        <Field label="VRChatユーザー名">
          <input
            className={inputClass}
            value={form.vrchat_username ?? ""}
            onChange={(e) => set("vrchat_username", e.target.value)}
            maxLength={64}
          />
        </Field>
        <Field label="主な参加プラットフォーム">
          <select
            className={inputClass}
            value={form.platform}
            onChange={(e) => set("platform", e.target.value)}
          >
            {PLATFORM_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="利用機材メモ">
          <input
            className={inputClass}
            value={form.device_note ?? ""}
            onChange={(e) => set("device_note", e.target.value)}
            maxLength={200}
            placeholder="例: Quest 3 + PC"
          />
        </Field>
        <Field label="X (旧Twitter) ID">
          <input
            className={inputClass}
            value={form.x_account ?? ""}
            onChange={(e) => set("x_account", e.target.value)}
            maxLength={50}
            placeholder="@なし"
          />
        </Field>
        <Field label="Discordユーザー名">
          <input
            className={inputClass}
            value={form.discord_account ?? ""}
            onChange={(e) => set("discord_account", e.target.value)}
            maxLength={64}
          />
        </Field>
        <Field label="自己紹介">
          <textarea
            className={inputClass}
            value={form.bio ?? ""}
            onChange={(e) => set("bio", e.target.value)}
            maxLength={500}
            rows={4}
          />
        </Field>
        <SubmitButton disabled={busy}>保存する</SubmitButton>
      </form>
    </div>
  );
}

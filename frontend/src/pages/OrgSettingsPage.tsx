import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  addMember,
  getOrganization,
  listMembers,
  removeMember,
  updateOrganization,
} from "../api/organizations";
import { ApiError } from "../api/client";
import {
  ErrorNote,
  Field,
  inputClass,
  SubmitButton,
  SuccessNote,
} from "../components/Form";
import { useMe } from "../lib/useMe";

export default function OrgSettingsPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { me } = useMe();
  const queryClient = useQueryClient();
  const isOwner =
    me?.organizations.find((o) => o.id === orgId)?.role === "owner";

  const orgQuery = useQuery({
    queryKey: ["org", orgId],
    queryFn: () => getOrganization(orgId!),
    enabled: !!orgId,
    retry: false,
  });
  const membersQuery = useQuery({
    queryKey: ["org-members", orgId],
    queryFn: () => listMembers(orgId!),
    enabled: !!orgId,
    retry: false,
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [orgError, setOrgError] = useState<string | null>(null);
  const [orgSaved, setOrgSaved] = useState(false);

  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<"owner" | "member">("member");
  const [memberError, setMemberError] = useState<string | null>(null);

  useEffect(() => {
    if (orgQuery.data) {
      setName(orgQuery.data.name);
      setDescription(orgQuery.data.description ?? "");
      setWebsiteUrl(orgQuery.data.website_url ?? "");
    }
  }, [orgQuery.data]);

  const saveOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    setOrgError(null);
    setOrgSaved(false);
    try {
      await updateOrganization(orgId!, {
        name,
        description: description || null,
        website_url: websiteUrl || null,
      });
      await queryClient.invalidateQueries({ queryKey: ["org", orgId] });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      setOrgSaved(true);
    } catch (err) {
      setOrgError(err instanceof ApiError ? err.message : "保存に失敗しました");
    }
  };

  const addMutation = useMutation({
    mutationFn: () => addMember(orgId!, { email: newEmail, role: newRole }),
    onSuccess: () => {
      setNewEmail("");
      queryClient.invalidateQueries({ queryKey: ["org-members", orgId] });
    },
    onError: (err) =>
      setMemberError(
        err instanceof ApiError ? err.message : "追加に失敗しました",
      ),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeMember(orgId!, userId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["org-members", orgId] }),
    onError: (err) =>
      setMemberError(
        err instanceof ApiError ? err.message : "除名に失敗しました",
      ),
  });

  if (orgQuery.isLoading) return <p className="text-slate-500">読み込み中...</p>;
  if (orgQuery.error) return <p className="text-slate-600">団体が見つかりません。</p>;
  const org = orgQuery.data!;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">団体設定: {org.name}</h1>
      <p className="text-sm text-slate-600">
        公開ページ:{" "}
        <a href={`/o/${org.slug}`} className="text-indigo-700 underline">
          /o/{org.slug}
        </a>{" "}
        ・ プラン: {org.plan}
      </p>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">基本情報</h2>
        {isOwner ? (
          <form onSubmit={saveOrg} className="space-y-4 rounded border bg-white p-4">
            <ErrorNote message={orgError} />
            <SuccessNote message={orgSaved ? "保存しました" : null} />
            <Field label="団体名" required>
              <input
                className={inputClass}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={100}
              />
            </Field>
            <Field label="紹介文">
              <textarea
                className={inputClass}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </Field>
            <Field label="WebサイトURL">
              <input
                className={inputClass}
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                maxLength={500}
              />
            </Field>
            <SubmitButton>保存する</SubmitButton>
          </form>
        ) : (
          <p className="text-sm text-slate-600">
            基本情報の編集は owner のみ可能です。
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">メンバー</h2>
        <ErrorNote message={memberError} />
        <div className="overflow-x-auto rounded border bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-2">メール</th>
                <th className="px-4 py-2">表示名</th>
                <th className="px-4 py-2">ロール</th>
                {isOwner && <th className="px-4 py-2"></th>}
              </tr>
            </thead>
            <tbody>
              {membersQuery.data?.map((m) => (
                <tr key={m.user_id} className="border-t">
                  <td className="px-4 py-2">{m.email}</td>
                  <td className="px-4 py-2">{m.display_name ?? "-"}</td>
                  <td className="px-4 py-2">{m.role}</td>
                  {isOwner && (
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => {
                          if (!window.confirm(`${m.email} を除名しますか?`)) return;
                          setMemberError(null);
                          removeMutation.mutate(m.user_id);
                        }}
                        className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
                      >
                        除名
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {isOwner && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setMemberError(null);
              addMutation.mutate();
            }}
            className="flex flex-wrap items-end gap-2 rounded border bg-white p-4"
          >
            <Field label="登録済みユーザーのメールアドレス">
              <input
                type="email"
                className={inputClass}
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
              />
            </Field>
            <Field label="ロール">
              <select
                className={inputClass}
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as "owner" | "member")}
              >
                <option value="member">member</option>
                <option value="owner">owner</option>
              </select>
            </Field>
            <SubmitButton disabled={addMutation.isPending}>追加</SubmitButton>
          </form>
        )}
      </section>
    </div>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getMe } from "../api/auth";
import { ApiError } from "../api/client";

// ログイン状態はこのクエリで一元管理。401 はログアウト状態として扱う
export function useMe() {
  const query = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 401) && failureCount < 2,
    staleTime: 60_000,
  });
  const loggedOut =
    query.error instanceof ApiError && query.error.status === 401;
  return { ...query, me: query.data ?? null, loggedOut };
}

export function useInvalidateMe() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["me"] });
}

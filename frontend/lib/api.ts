import { createClient } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

async function apiFetch(path: string, token: string, options?: RequestInit): Promise<unknown> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
  });

  if (res.status === 401) {
    // Try to refresh the session once before giving up
    const supabase = createClient();
    const { data } = await supabase.auth.refreshSession();
    if (data.session) {
      const retry = await fetch(`${API_URL}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${data.session.access_token}`,
          ...(options?.headers ?? {}),
        },
      });
      if (retry.ok) return retry.json();
      if (retry.status !== 401) throw new Error(`API error ${retry.status}`);
    }
    // Redirect to login if refresh fails or retry is also 401
    if (typeof window !== "undefined") window.location.href = "/";
    throw new Error("Session expired");
  }

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export const api = {
  getMatches: (token: string, page = 1, pageSize = 20) =>
    apiFetch(`/matches?page=${page}&page_size=${pageSize}`, token) as Promise<{
      matches: object[];
      total: number;
      page: number;
      page_size: number;
    }>,
  getProfile: (token: string) => apiFetch("/profile", token),
  saveProfile: (token: string, body: object) =>
    apiFetch("/profile", token, { method: "POST", body: JSON.stringify(body) }),
  rematch: (token: string) =>
    apiFetch("/rematch", token, { method: "POST" }),
};

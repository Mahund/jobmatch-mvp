const API_URL = process.env.NEXT_PUBLIC_API_URL;

async function apiFetch(path: string, token: string, options?: RequestInit) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export const api = {
  getMatches: (token: string) => apiFetch("/matches", token),
  getProfile: (token: string) => apiFetch("/profile", token),
  saveProfile: (token: string, body: object) =>
    apiFetch("/profile", token, { method: "POST", body: JSON.stringify(body) }),
  rematch: (token: string) =>
    apiFetch("/rematch", token, { method: "POST" }),
};

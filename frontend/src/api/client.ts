const BASE_URL = "/api";

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: (path: string) =>
    request(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    fetch(`${BASE_URL}${path}`, { method: "POST", body: formData }).then(
      async (res) => {
        if (!res.ok) {
          const error = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(error.detail || `HTTP ${res.status}`);
        }
        return res.json() as Promise<T>;
      },
    ),
};

const env = import.meta.env ?? {};

export function normalizeApiBaseUrl(value = "") {
  return String(value ?? "").replace(/\/$/, "");
}

export function apiPath(path, baseUrl = normalizeApiBaseUrl(env.VITE_API_BASE_URL ?? "")) {
  const normalizedBaseUrl = normalizeApiBaseUrl(baseUrl);
  return normalizedBaseUrl ? `${normalizedBaseUrl}${path}` : path;
}

function headersToObject(headers = {}) {
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return { ...headers };
}

export function buildApiHeaders({ token = env.VITE_API_TOKEN ?? "", headers = {} } = {}) {
  const nextHeaders = headersToObject(headers);
  const trimmedToken = String(token ?? "").trim();
  if (trimmedToken && !nextHeaders.Authorization && !nextHeaders.authorization) {
    nextHeaders.Authorization = `Bearer ${trimmedToken}`;
  }
  return nextHeaders;
}

export function apiFetch(path, options = {}) {
  return fetch(apiPath(path), {
    ...options,
    headers: buildApiHeaders({ headers: options.headers }),
  });
}

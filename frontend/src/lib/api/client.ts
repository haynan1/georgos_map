import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema.gen";

export type Schemas = components["schemas"];

/**
 * Typed HTTP client generated from the API's OpenAPI document (`pnpm gen:api`).
 *
 * Same-origin only: the session lives in an HttpOnly cookie the browser attaches
 * automatically; JavaScript never sees it. State-changing requests carry the per-session
 * CSRF token, which is held in memory only (never in localStorage).
 */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "",
  credentials: "same-origin",
  // Resolved per call (not captured at import) so tests and instrumentation can wrap it.
  fetch: (request) => globalThis.fetch(request),
});

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (csrfToken && UNSAFE_METHODS.has(request.method)) {
      request.headers.set("X-CSRF-Token", csrfToken);
    }
    return request;
  },
};

api.use(csrfMiddleware);

export interface FieldIssue {
  loc: string[];
  message: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly fields: FieldIssue[] = [],
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toApiError(status: number, body: unknown): ApiError {
  const error = isRecord(body) && isRecord(body.error) ? body.error : null;
  if (!error) {
    return new ApiError(status, "unexpected_response", "Resposta inesperada do servidor.");
  }
  return new ApiError(
    status,
    typeof error.code === "string" ? error.code : "unknown_error",
    typeof error.message === "string" ? error.message : "Não foi possível concluir a ação.",
    Array.isArray(error.fields) ? (error.fields as FieldIssue[]) : [],
    typeof error.request_id === "string" ? error.request_id : null,
  );
}

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Resolve an openapi-fetch call to its data, or throw a typed ApiError. */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await call;
  } catch {
    throw new ApiError(0, "network_error", "Sem conexão com o servidor. Verifique sua internet.");
  }
  if (!result.response.ok) {
    throw toApiError(result.response.status, result.error);
  }
  return result.data as T;
}

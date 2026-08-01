const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!configuredApiBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not configured.");
}

const apiBaseUrl = configuredApiBaseUrl.replace(/\/+$/, "");

export const SESSION_EXPIRED_MESSAGE =
  "Your session expired. Please sign in again.";

type AuthenticationFailureHandler = (rejectedToken: string) => void;

let authenticationFailureHandler: AuthenticationFailureHandler | null = null;

interface ApiRequestOptions {
  accept?: string;
  method?: "GET" | "POST";
  body?: unknown;
  token?: string;
  signal?: AbortSignal;
}

interface ErrorEnvelope {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly details: unknown;

  constructor(
    status: number,
    message: string,
    code: string | null = null,
    details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const response = await sendRequest(path, options);
  const responseBody = await parseResponseBody(response);

  if (!response.ok) {
    throwResponseError(response, responseBody, options.token);
  }

  return responseBody as T;
}

export async function apiStreamRequest(
  path: string,
  options: ApiRequestOptions = {},
): Promise<Response> {
  const response = await sendRequest(path, options);
  if (!response.ok) {
    const responseBody = await parseResponseBody(response);
    throwResponseError(response, responseBody, options.token);
  }
  return response;
}

async function sendRequest(
  path: string,
  options: ApiRequestOptions,
): Promise<Response> {
  const headers = new Headers({
    Accept: options.accept ?? "application/json",
  });
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  return fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
}

export function registerAuthenticationFailureHandler(
  handler: AuthenticationFailureHandler,
): () => void {
  authenticationFailureHandler = handler;

  return () => {
    if (authenticationFailureHandler === handler) {
      authenticationFailureHandler = null;
    }
  };
}

export function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function throwResponseError(
  response: Response,
  responseBody: unknown,
  token: string | undefined,
): never {
  if (response.status === 401 && token) {
    authenticationFailureHandler?.(token);
    throw new ApiError(401, SESSION_EXPIRED_MESSAGE, "session_expired");
  }

  const envelope = isRecord(responseBody) ? (responseBody as ErrorEnvelope) : null;
  const message =
    typeof envelope?.error?.message === "string"
      ? envelope.error.message
      : `Request failed with status ${response.status}.`;
  const code =
    typeof envelope?.error?.code === "string" ? envelope.error.code : null;
  throw new ApiError(response.status, message, code, envelope?.error?.details);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!configuredApiBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not configured.");
}

const apiBaseUrl = configuredApiBaseUrl.replace(/\/+$/, "");

interface ApiRequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  token?: string;
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
  const headers = new Headers({ Accept: "application/json" });
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const responseBody = await parseResponseBody(response);

  if (!response.ok) {
    const envelope = isRecord(responseBody)
      ? (responseBody as ErrorEnvelope)
      : null;
    const message =
      typeof envelope?.error?.message === "string"
        ? envelope.error.message
        : `Request failed with status ${response.status}.`;
    const code =
      typeof envelope?.error?.code === "string" ? envelope.error.code : null;
    throw new ApiError(
      response.status,
      message,
      code,
      envelope?.error?.details,
    );
  }

  return responseBody as T;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

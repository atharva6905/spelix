/**
 * Shared typed transport error for every `@/api/*` module (issue #283,
 * follow-up to #235).
 *
 * Before #283, each API module hand-rolled a `{ status, ...(body.detail ?? body) }`
 * object-literal throw (and `analyses.ts` additionally diverged on precedence
 * with `body.error ?? body.detail ?? body`). Hand-rolled rejections hid throw-shape
 * drift from both tsc and vitest. {@link ApiError} is a real `Error` subclass so
 * consumers can use `instanceof Error`/`err.message`, and {@link isApiError} pins
 * them to the actual transport shape.
 *
 * `buildApiError` preserves every pre-#283 consumer behaviour, including the
 * `analyses.ts` core-path's top-level `body.error.{code,message}` read.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly detail?: unknown;

  constructor(args: { status: number; message: string; code?: string; detail?: unknown }) {
    super(args.message);
    this.name = "ApiError";
    this.status = args.status;
    this.code = args.code;
    this.detail = args.detail;
  }
}

/**
 * Type guard for {@link ApiError}. Uses `instanceof` first, then duck-types on
 * `name === "ApiError"` + numeric `status` so the guard survives any
 * transpile/realm boundary where `instanceof` could fail.
 */
export function isApiError(e: unknown): e is ApiError {
  if (e instanceof ApiError) return true;
  return (
    typeof e === "object" &&
    e !== null &&
    (e as { name?: unknown }).name === "ApiError" &&
    typeof (e as { status?: unknown }).status === "number"
  );
}

function asString(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}

/**
 * Build an {@link ApiError} from a parsed error body. Never throws from the
 * error path itself — every unexpected shape falls back to a safe message.
 *
 * Precedence (preserving all pre-#283 surfaces):
 *   1. FastAPI structured error: `{ detail: { error: { code, message } } }`
 *   2. Plain detail object: `{ detail: { code, message } }`
 *   3. Pydantic validation array: `{ detail: [{ loc, msg, type }] }` (no code)
 *   4. Plain string detail: `{ detail: "..." }`
 *   5. Top-level structured error: `{ error: { code, message } }`
 *      (the `analyses.ts` core-path divergence — `body.error` first)
 *   6. Top-level `{ code, message }`
 *   7. Safe fallback
 */
export function buildApiError(status: number, body: unknown): ApiError {
  const fallback = `Request failed (HTTP ${status}).`;
  const isObj = typeof body === "object" && body !== null;
  const detail = isObj ? (body as { detail?: unknown }).detail : undefined;

  // (1)/(2) detail is a plain object.
  if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
    const errObj = (detail as { error?: unknown }).error;
    if (typeof errObj === "object" && errObj !== null) {
      return new ApiError({
        status,
        code: asString((errObj as { code?: unknown }).code),
        message: asString((errObj as { message?: unknown }).message) ?? fallback,
        detail,
      });
    }
    return new ApiError({
      status,
      code: asString((detail as { code?: unknown }).code),
      message: asString((detail as { message?: unknown }).message) ?? fallback,
      detail,
    });
  }

  // (3) Pydantic validation: detail is an array of {loc, msg, type}. No code.
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    return new ApiError({ status, message: asString(first?.msg) ?? fallback, detail });
  }

  // (4) Plain string detail.
  if (typeof detail === "string") {
    return new ApiError({ status, message: detail, detail });
  }

  // (5) Top-level structured error `{ error: { code, message } }` — preserves the
  // pre-#283 analyses.ts `body.error ?? ...` precedence.
  if (isObj) {
    const errObj = (body as { error?: unknown }).error;
    if (typeof errObj === "object" && errObj !== null) {
      return new ApiError({
        status,
        code: asString((errObj as { code?: unknown }).code),
        message: asString((errObj as { message?: unknown }).message) ?? fallback,
      });
    }

    // (6) Top-level `{ code, message }`.
    return new ApiError({
      status,
      code: asString((body as { code?: unknown }).code),
      message: asString((body as { message?: unknown }).message) ?? fallback,
    });
  }

  // (7) Safe fallback.
  return new ApiError({ status, message: fallback });
}

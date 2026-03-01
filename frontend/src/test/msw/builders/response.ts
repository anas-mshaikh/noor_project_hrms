/**
 * test/msw/builders/response.ts
 *
 * Helpers to build backend-shaped response envelopes consistently in tests.
 */

export type EnvelopeOk<T> = { ok: true; data: T; meta?: unknown };
export type EnvelopeErr = {
  ok: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
    correlation_id?: string;
  };
};

export function ok<T>(data: T, meta?: unknown): EnvelopeOk<T> {
  return meta === undefined ? { ok: true, data } : { ok: true, data, meta };
}

export function fail(
  code: string,
  message: string,
  opts?: { details?: unknown; correlation_id?: string }
): EnvelopeErr {
  return {
    ok: false,
    error: {
      code,
      message,
      ...(opts?.details !== undefined ? { details: opts.details } : {}),
      ...(opts?.correlation_id ? { correlation_id: opts.correlation_id } : {}),
    },
  };
}

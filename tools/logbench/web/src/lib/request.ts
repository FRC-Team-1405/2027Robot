// Bound requests and surface HTTP, JSON and network errors through the same UI path.
export async function requestJson(url: string, options: RequestInit = {}, timeoutMs = 10000): Promise<unknown> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    let body: unknown;
    try { body = await response.json(); } catch {
      throw new Error(response.ok ? 'The server returned invalid JSON.' : `Server error (HTTP ${response.status}).`);
    }
    if (!response.ok) {
      const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
      throw new Error(typeof detail === 'string' ? detail : `Server error (HTTP ${response.status}).`);
    }
    return body;
  } catch (error) {
    if (controller.signal.aborted && !options.signal?.aborted) throw new Error('The server request timed out.');
    throw error;
  } finally {
    window.clearTimeout(timer);
    options.signal?.removeEventListener('abort', abort);
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export interface Parsed<T> { value: T; warnings: string[] }

export interface RetryableCache<T> {
  get(forceRefresh?: boolean): Promise<T>;
}

export async function withAbortTimeout<T>(
  load: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await load(controller.signal);
  } finally {
    clearTimeout(timeout);
  }
}

export function createRetryableCache<T>(
  load: () => Promise<T>,
  ttlMs: number,
  now: () => number = Date.now,
): RetryableCache<T> {
  let cache: { value: T; expiresAt: number } | null = null;
  let request: Promise<T> | null = null;
  let generation = 0;

  return {
    get(forceRefresh = false) {
      if (forceRefresh) {
        generation += 1;
        cache = null;
        request = null;
      }

      const currentTime = now();
      if (cache && cache.expiresAt > currentTime) return Promise.resolve(cache.value);
      if (request) return request;

      const requestGeneration = generation;
      const pending = load()
        .then((value) => {
          if (requestGeneration === generation) {
            cache = { value, expiresAt: now() + ttlMs };
          }
          return value;
        })
        .finally(() => {
          if (request === pending) request = null;
        });
      request = pending;
      return pending;
    },
  };
}

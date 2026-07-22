import assert from "node:assert/strict";
import { it } from "node:test";

import { createRetryableCache, withAbortTimeout } from "./retryable-cache.ts";

it("retries AI status after a failed request and only caches successful responses", async () => {
  let requestCount = 0;
  const status = createRetryableCache(async () => {
    requestCount += 1;
    if (requestCount === 1) throw new Error("temporary network failure");
    return { enabled: requestCount === 2 };
  }, 30_000);

  await assert.rejects(status.get(), /temporary network failure/);
  assert.deepEqual(await status.get(), { enabled: true });
  assert.deepEqual(await status.get(), { enabled: true });
  assert.equal(requestCount, 2, "a successful status should be cached");

  assert.deepEqual(await status.get(true), { enabled: false });
  assert.equal(requestCount, 3, "an explicit retry should bypass the success cache");
});

it("aborts a status loader that does not settle before its timeout", async () => {
  let observedAbort = false;
  await assert.rejects(
    withAbortTimeout(
      (signal) => new Promise((resolve, reject) => {
        signal.addEventListener("abort", () => {
          observedAbort = true;
          reject(new Error("status request aborted"));
        }, { once: true });
      }),
      10,
    ),
    /status request aborted/,
  );
  assert.equal(observedAbort, true);
});

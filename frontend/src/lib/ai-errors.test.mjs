import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { parseAiError } from "./ai-errors.ts";

function headers(values = {}) {
  const normalized = Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key.toLowerCase(), value]),
  );
  return {
    get(name) {
      return normalized[name.toLowerCase()] ?? null;
    },
  };
}

describe("AI error contract", () => {
  it("keeps an output-only block separate from content moderation", () => {
    assert.deepEqual(
      parseAiError({ detail: "AI_OUTPUT_BLOCKED" }, headers()),
      { code: "AI_OUTPUT_BLOCKED", moderationUpdate: null },
    );
  });

  it("reads an explicit structured moderation transition", () => {
    assert.deepEqual(
      parseAiError({
        code: "POLITICAL_CONTENT_REVIEW_PENDING",
        moderation_update: {
          content_id: "content-1",
          status: "pending_review",
          reason: "political_or_uncertain",
          revision_number: 3,
          target_href: "/posts/content-1",
        },
      }, headers()),
      {
        code: "POLITICAL_CONTENT_REVIEW_PENDING",
        moderationUpdate: {
          contentId: "content-1",
          status: "pending_review",
          reason: "political_or_uncertain",
          revisionNumber: 3,
          targetHref: "/posts/content-1",
        },
      },
    );
  });

  it("supports the compatible response-header contract", () => {
    const result = parseAiError(
      { detail: "POLITICAL_CONTENT_REVIEW_PENDING" },
      headers({
        "X-Agora-Moderation-Status": "pending_review",
        "X-Agora-Content-Id": "content-2",
        "X-Agora-Moderation-Reason": "political_or_uncertain",
        "X-Agora-Revision-Number": "4",
        "X-Agora-Target-Href": "/posts/content-2",
      }),
    );

    assert.equal(result.moderationUpdate?.contentId, "content-2");
    assert.equal(result.moderationUpdate?.revisionNumber, 4);
    assert.equal(result.moderationUpdate?.targetHref, "/posts/content-2");
  });

  it("ignores incomplete or unsafe moderation metadata", () => {
    assert.equal(
      parseAiError(
        {
          detail: {
            code: "POLITICAL_CONTENT_REVIEW_PENDING",
            moderation_update: {
              status: "pending_review",
              target_href: "https://example.com/posts/1",
            },
          },
        },
        headers(),
      ).moderationUpdate,
      null,
    );
  });
});

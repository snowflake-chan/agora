import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { hasModerationNotice, moderationTargetContentId } from "./moderation.ts";

describe("moderation event targets", () => {
  it("treats a root-post event as targeting the post", () => {
    assert.equal(
      moderationTargetContentId(
        { type: "moderation_pending", link: "/posts/post-1" },
        "post-1",
      ),
      "post-1",
    );
  });

  it("keeps a comment event separate from its root post", () => {
    assert.equal(
      moderationTargetContentId(
        { type: "moderation_pending", link: "/posts/post-1#comment-2" },
        "post-1",
      ),
      "comment-2",
    );
  });

  it("prefers explicit content identity over a fallback link", () => {
    assert.equal(
      moderationTargetContentId(
        {
          type: "moderation_pending",
          link: "/posts/post-1",
          contentId: "comment-3",
        },
        "post-1",
      ),
      "comment-3",
    );
  });
});

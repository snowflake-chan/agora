import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  POLL_AI_MIN_BODY_LENGTH,
  POLL_AI_MIN_TITLE_LENGTH,
  WRITING_ASSIST_MIN_BODY_LENGTH,
  createAiInputSignature,
  getPollAiReadiness,
  getWritingAssistReadiness,
  isCurrentAiResult,
} from "./ai-ui.ts";

describe("AI tool input readiness", () => {
  it("keeps writing assistance available at the documented boundary", () => {
    assert.deepEqual(getWritingAssistReadiness(" short "), {
      ready: false,
      titleRemaining: 0,
      bodyRemaining: WRITING_ASSIST_MIN_BODY_LENGTH - 5,
    });
    assert.equal(
      getWritingAssistReadiness("x".repeat(WRITING_ASSIST_MIN_BODY_LENGTH)).ready,
      true,
    );
  });

  it("reports title and body requirements independently for poll generation", () => {
    assert.deepEqual(getPollAiReadiness("Idea", "Context"), {
      ready: false,
      titleRemaining: POLL_AI_MIN_TITLE_LENGTH - 4,
      bodyRemaining: POLL_AI_MIN_BODY_LENGTH - 7,
    });
    assert.deepEqual(
      getPollAiReadiness(
        "x".repeat(POLL_AI_MIN_TITLE_LENGTH),
        "y".repeat(POLL_AI_MIN_BODY_LENGTH),
      ),
      { ready: true, titleRemaining: 0, bodyRemaining: 0 },
    );
  });

  it("does not count surrounding whitespace as useful context", () => {
    assert.equal(getWritingAssistReadiness(`  ${"x".repeat(11)}  `).ready, false);
    assert.equal(getPollAiReadiness("        ", " ".repeat(50)).ready, false);
  });

  it("rejects an AI response when its request or source input is stale", () => {
    const requested = createAiInputSignature(["Title", "Original body", "en"]);
    const changed = createAiInputSignature(["Title", "Edited body", "en"]);

    assert.equal(isCurrentAiResult(4, 4, requested, requested), true);
    assert.equal(isCurrentAiResult(3, 4, requested, requested), false);
    assert.equal(isCurrentAiResult(4, 4, requested, changed), false);
  });
});

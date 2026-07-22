import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { localizeNotification, messages } from "./i18n.ts";
import {
  formatVotingPeriod,
  getVotingCountdown,
  isActiveCreatorWindow,
  resolveVotingPeriodHours,
} from "./governance.ts";
import {
  normalizeColorMode,
  normalizeHomeLayout,
  normalizeMotion,
  normalizeTheme,
} from "./preferences.ts";

const locales = ["en", "ja", "zh-TW"];

function placeholders(value) {
  return [...value.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
}

describe("translation catalog", () => {
  it("keeps every locale aligned with the English catalog", () => {
    const englishKeys = Object.keys(messages.en).sort();

    for (const locale of locales) {
      assert.deepEqual(Object.keys(messages[locale]).sort(), englishKeys);
      for (const key of englishKeys) {
        assert.notEqual(messages[locale][key].trim(), "", `${locale}.${key}`);
        assert.deepEqual(
          placeholders(messages[locale][key]),
          placeholders(messages.en[key]),
          `${locale}.${key}`,
        );
      }
    }
  });

  it("ships complete localized copy for the About page", () => {
    const aboutKeys = Object.keys(messages.en).filter(
      (key) => key === "nav.about" || key.startsWith("about."),
    );

    assert.ok(aboutKeys.length > 20);
    for (const locale of locales) {
      for (const key of aboutKeys) {
        assert.equal(typeof messages[locale][key], "string", `${locale}.${key}`);
        assert.notEqual(messages[locale][key].trim(), "", `${locale}.${key}`);
      }
    }
  });

  it("ships aligned poll and AI assistance copy in every supported locale", () => {
    const featureKeys = Object.keys(messages.en).filter(
      (key) => key.startsWith("poll.") || key.startsWith("ai."),
    );

    assert.ok(featureKeys.length > 35);
    for (const locale of locales) {
      for (const key of featureKeys) {
        assert.equal(typeof messages[locale][key], "string", `${locale}.${key}`);
        assert.notEqual(messages[locale][key].trim(), "", `${locale}.${key}`);
      }
      assert.match(messages[locale]["ai.politicalUnavailable"], /AI/i);
      assert.notEqual(messages[locale]["ai.translate"], messages[locale]["ai.hideResult"]);
      assert.match(messages[locale]["ai.reviewPendingDescription"], /AI/i);
    }
  });

  it("ships complete AI moderation workflow copy in every supported locale", () => {
    const moderationKeys = Object.keys(messages.en).filter(
      (key) => key.startsWith("moderation.ai.") || key.startsWith("admin.moderation"),
    );

    assert.ok(moderationKeys.length > 20);
    for (const locale of locales) {
      for (const key of moderationKeys) {
        assert.equal(typeof messages[locale][key], "string", `${locale}.${key}`);
        assert.notEqual(messages[locale][key].trim(), "", `${locale}.${key}`);
      }
      assert.match(messages[locale]["moderation.ai.pendingDescription"], /AI|automated|自動/i);
    }
  });

  it("localizes system notifications without exposing stored source copy", () => {
    const translate = (key) => messages.ja[key] ?? messages.en[key] ?? key;
    const localized = localizeNotification(
      { type: "reply", message: "Stored server message" },
      translate,
    );

    assert.equal(localized.title, messages.ja["notifications.event.newReplyTitle"]);
    assert.equal(localized.message, messages.ja["notifications.event.newReplyMessage"]);
    assert.doesNotMatch(localized.message, /Stored server message/);
  });

  it("preserves user-authored titles in following notifications", () => {
    const translate = (key) => messages["zh-TW"][key] ?? messages.en[key] ?? key;
    const localized = localizeNotification(
      { type: "following_post", message: "A user-authored title" },
      translate,
    );

    assert.equal(
      localized.title,
      messages["zh-TW"]["notifications.event.followingPostTitle"],
    );
    assert.equal(localized.message, "A user-authored title");
  });

  it("localizes moderation notifications and preserves only the review note", () => {
    const translate = (key, params) => {
      const template = messages["zh-TW"][key] ?? messages.en[key] ?? key;
      return template.replace(/\{(\w+)\}/g, (match, name) =>
        Object.hasOwn(params ?? {}, name) ? String(params[name]) : match,
      );
    };
    const pending = localizeNotification(
      { type: "moderation_pending", message: "political_or_uncertain" },
      translate,
    );
    const unavailable = localizeNotification(
      { type: "moderation_pending", message: "classifier_unavailable" },
      translate,
    );
    const rejected = localizeNotification(
      {
        type: "moderation_rejected",
        message: "請刪除具體人名後重新發佈。",
      },
      translate,
    );
    const approved = localizeNotification(
      {
        type: "moderation_approved",
        message: "已移除不確定內容。",
      },
      translate,
    );

    assert.equal(pending.title, messages["zh-TW"]["notifications.event.moderationPendingTitle"]);
    assert.equal(pending.message, messages["zh-TW"]["notifications.event.moderationPendingMessage"]);
    assert.doesNotMatch(pending.message, /political_or_uncertain/);
    assert.equal(
      unavailable.message,
      messages["zh-TW"]["notifications.event.moderationPendingUnavailableMessage"],
    );
    assert.doesNotMatch(unavailable.message, /classifier_unavailable/);
    assert.equal(rejected.title, messages["zh-TW"]["notifications.event.moderationRejectedTitle"]);
    assert.match(rejected.message, /管理員備註/);
    assert.match(rejected.message, /請刪除具體人名後重新發佈/);
    assert.doesNotMatch(rejected.message, /Your content was not approved/);
    assert.equal(approved.title, messages["zh-TW"]["notifications.event.moderationApprovedTitle"]);
    assert.match(approved.message, /已移除不確定內容/);
    assert.doesNotMatch(approved.message, /Your content passed review/);
  });
});

describe("preference normalization", () => {
  it("accepts supported values and falls back safely", () => {
    assert.equal(normalizeTheme("claude"), "claude");
    assert.equal(normalizeTheme("invalid"), "default");
    assert.equal(normalizeMotion("reduced"), "reduced");
    assert.equal(normalizeMotion("invalid"), "system");
    assert.equal(normalizeColorMode("light"), "light");
    assert.equal(normalizeColorMode("invalid"), "dark");
    assert.equal(normalizeHomeLayout("pages"), "pages");
    assert.equal(normalizeHomeLayout("invalid"), "split");
  });
});

describe("governance window presentation", () => {
  const startedAt = "2026-07-20T00:00:00.000Z";
  const startedAtMs = Date.parse(startedAt);
  const endsAt = "2026-07-21T00:00:00.000Z";

  it("uses the server period and falls back to the persisted timestamps", () => {
    assert.equal(resolveVotingPeriodHours(72, startedAt, endsAt), 72);
    assert.equal(resolveVotingPeriodHours(null, startedAt, endsAt), 24);
    assert.equal(resolveVotingPeriodHours(null, null, endsAt), null);
    assert.equal(isActiveCreatorWindow("active_creator", 24, startedAt, endsAt), true);
    assert.equal(isActiveCreatorWindow("standard", 24, startedAt, endsAt), false);
  });

  it("rounds remaining voting time upward and closes exactly at the deadline", () => {
    assert.deepEqual(getVotingCountdown(endsAt, startedAtMs + 1), {
      state: "days",
      days: 1,
      hours: 0,
    });
    assert.deepEqual(getVotingCountdown(endsAt, Date.parse(endsAt) - 30_000), {
      state: "minutes",
      minutes: 1,
    });
    assert.deepEqual(getVotingCountdown(endsAt, Date.parse(endsAt)), {
      state: "closed",
    });
  });

  it("formats persisted periods in the selected locale", () => {
    assert.match(formatVotingPeriod(24, "en") ?? "", /1\s*day/i);
    assert.match(formatVotingPeriod(72, "en") ?? "", /3\s*days/i);
  });
});

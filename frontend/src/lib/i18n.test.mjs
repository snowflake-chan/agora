import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { localizeNotification, messages } from "./i18n.ts";
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

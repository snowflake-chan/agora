import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  detectFieldsLocale,
  detectSupportedLocale,
  shouldRequestTranslation,
} from "./language.ts";

describe("local translation language detection", () => {
  it("recognizes clear English, Japanese, and Traditional Chinese text", () => {
    assert.equal(detectSupportedLocale("A concise release note"), "en");
    assert.equal(detectSupportedLocale("\u3053\u308c\u306f\u516c\u958b\u524d\u306e\u6587\u7ae0\u3067\u3059"), "ja");
    assert.equal(detectSupportedLocale("\u9019\u662f\u4e00\u7bc7\u7e41\u9ad4\u4e2d\u6587\u5167\u5bb9"), "zh-TW");
  });

  it("keeps ambiguous Han-only and non-linguistic text eligible for translation", () => {
    assert.equal(detectSupportedLocale("\u6295\u7968"), null);
    assert.equal(detectSupportedLocale("2026-07-21"), null);
  });

  it("skips only when every populated field is clearly in the target language", () => {
    const english = [{ text: "Release candidate" }, { text: "Ready for review." }];
    assert.equal(detectFieldsLocale(english), "en");
    assert.equal(shouldRequestTranslation(english, "en"), false);
    assert.equal(shouldRequestTranslation(english, "ja"), true);
  });

  it("does not skip mixed or uncertain title and body fields", () => {
    assert.equal(
      detectFieldsLocale([{ text: "Release candidate" }, { text: "\u3053\u308c\u306f\u65e5\u672c\u8a9e\u306e\u6587\u7ae0\u3067\u3059" }]),
      null,
    );
    assert.equal(
      shouldRequestTranslation([{ text: "\u6295\u7968" }, { text: "\u9019\u662f\u7e41\u9ad4\u4e2d\u6587" }], "zh-TW"),
      true,
    );
  });
});

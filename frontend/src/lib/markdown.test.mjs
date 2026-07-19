import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { renderMarkdown } from "./markdown.js";

describe("renderMarkdown", () => {
  it("preserves ordinary Markdown", () => {
    const html = renderMarkdown(
      "# Heading\n\n**bold** and [link](https://example.com)"
    );

    assert.match(html, /<h1>Heading<\/h1>/);
    assert.match(html, /<strong>bold<\/strong>/);
    assert.match(html, /href="https:\/\/example\.com"/);
  });

  it("removes scripts and inline event handlers", () => {
    const html = renderMarkdown(
      '<img src="https://example.com/a.png" onerror="alert(1)">'
      + '<script>globalThis.pwned = true</script>'
    );

    assert.match(html, /src="https:\/\/example\.com\/a\.png"/);
    assert.doesNotMatch(html, /onerror/);
    assert.doesNotMatch(html, /<script/);
    assert.doesNotMatch(html, /globalThis\.pwned/);
  });

  it("removes dangerous URL schemes", () => {
    const html = renderMarkdown(
      '[click](javascript:alert(1))'
      + '<img src="data:text/html,<script>alert(1)</script>">'
    );

    assert.doesNotMatch(html, /javascript:/);
    assert.doesNotMatch(html, /data:/);
  });
});

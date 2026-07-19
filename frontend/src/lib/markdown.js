import { marked } from "marked";
import sanitizeHtml from "sanitize-html";

const allowedTags = [...sanitizeHtml.defaults.allowedTags, "img"];
const allowedAttributes = {
  ...sanitizeHtml.defaults.allowedAttributes,
  a: ["href", "name", "target", "rel"],
  img: ["src", "alt", "title", "width", "height"],
};

/**
 * Render user-authored Markdown without allowing executable HTML.
 *
 * This function is safe in both Astro's Node SSR process and the browser.
 */
/**
 * @param {string} source
 * @returns {string}
 */
export function renderMarkdown(source) {
  const rendered = marked.parse(source, {
    async: false,
    breaks: true,
    gfm: true,
  });

  return sanitizeHtml(rendered, {
    allowedTags,
    allowedAttributes,
    allowedSchemes: ["http", "https", "mailto"],
    allowedSchemesByTag: {
      img: ["http", "https"],
    },
    allowProtocolRelative: false,
    transformTags: {
      a: sanitizeHtml.simpleTransform("a", {
        rel: "nofollow noopener noreferrer",
      }),
    },
  });
}

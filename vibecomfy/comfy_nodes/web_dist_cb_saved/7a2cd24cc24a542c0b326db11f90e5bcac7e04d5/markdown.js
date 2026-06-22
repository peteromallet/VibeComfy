// Lightweight, XSS-safe markdown renderer for agent chat messages.
// Parses a subset of CommonMark into DOM nodes rather than raw HTML so that
// arbitrary text cannot inject scripts or unwanted markup.

const BLOCK_RE = /^(#{1,6})\s+(.*)$/;
const CODE_FENCE_RE = /^```(\w*)\s*$/;
const UL_RE = /^[-*]\s+(.*)$/;
const OL_RE = /^(\d+)\.\s+(.*)$/;

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function createTextNode(document, text) {
  if (typeof document.createTextNode === "function") {
    return document.createTextNode(text);
  }
  // Fallback for minimal test harnesses: return a span whose textContent is
  // the escaped text. This keeps the rendered tree inspectable in tests that
  // do not implement createTextNode.
  const node = document.createElement("span");
  node.textContent = text;
  return node;
}

function setNodeText(document, node, text) {
  node.textContent = text;
}

const STYLE_STRONG = {
  fontWeight: "700",
  color: "#edf2f7",
};

const STYLE_EM = {
  fontStyle: "italic",
  color: "#e2e8f0",
};

const STYLE_DEL = {
  textDecoration: "line-through",
  opacity: "0.75",
};

const STYLE_CODE = {
  fontFamily: "monospace",
  fontSize: "0.92em",
  background: "#1a1d25",
  color: "#e2e8f0",
  padding: "1px 4px",
  borderRadius: "3px",
  border: "1px solid #2d3340",
};

const STYLE_LINK = {
  color: "#9ed0ff",
  textDecoration: "none",
};

function applyStyle(node, styles) {
  Object.assign(node.style, styles);
}

const SAFE_URL_SCHEMES = new Set(["http:", "https:", "mailto:"]);

function isSafeUrl(url) {
  try {
    const normalized = String(url).trim();
    if (/[\u0000-\u001f\u007f]/.test(normalized)) {
      return false;
    }
    const lower = normalized.toLowerCase();
    // Allow relative paths and fragment-only URLs (same-page anchors). Protocol-
    // relative URLs are treated as external URLs and must use an explicit scheme.
    if (lower === "" || lower.startsWith("#")) {
      return true;
    }
    if (lower.startsWith("/") && !lower.startsWith("//")) {
      return true;
    }
    if (!/^[a-z][a-z0-9+.-]*:/i.test(normalized)) {
      return !lower.startsWith("//");
    }
    const parsed = new URL(lower, "http://localhost");
    return SAFE_URL_SCHEMES.has(parsed.protocol);
  } catch (_error) {
    // If parsing fails, treat as unsafe.
    return false;
  }
}

function parseInline(document, text) {
  const nodes = [];

  const patterns = [
    { re: /\\\n/g, handler: () => document.createElement("br") },
    { re: /`([^`]+)`/g, handler: (match) => {
      const code = document.createElement("code");
      applyStyle(code, STYLE_CODE);
      setNodeText(document, code, match[1]);
      return code;
    } },
    { re: /\*\*([^*]+)\*\*/g, handler: (match) => {
      const strong = document.createElement("strong");
      applyStyle(strong, STYLE_STRONG);
      parseInlineInto(document, match[1], strong);
      return strong;
    } },
    { re: /__([^_]+)__/g, handler: (match) => {
      const strong = document.createElement("strong");
      applyStyle(strong, STYLE_STRONG);
      parseInlineInto(document, match[1], strong);
      return strong;
    } },
    { re: /(?<![\w*])\*([^*]+)\*(?![\w*])/g, handler: (match) => {
      const em = document.createElement("em");
      applyStyle(em, STYLE_EM);
      parseInlineInto(document, match[1], em);
      return em;
    } },
    { re: /(?<![\w_])_([^_]+)_(?![\w_])/g, handler: (match) => {
      const em = document.createElement("em");
      applyStyle(em, STYLE_EM);
      parseInlineInto(document, match[1], em);
      return em;
    } },
    { re: /~~([^~]+)~~/g, handler: (match) => {
      const del = document.createElement("del");
      applyStyle(del, STYLE_DEL);
      parseInlineInto(document, match[1], del);
      return del;
    } },
    { re: /\[([^\]]+)\]\(((?:\\.|[^()\\]|\([^()]*\))+)\)/g, handler: (match) => {
      const label = match[1];
      const url = match[2];
      if (!isSafeUrl(url)) {
        // Unsafe URL: render the label as plain text with a subtle marker.
        const span = document.createElement("span");
        applyStyle(span, { opacity: "0.75" });
        parseInlineInto(document, `${label}`, span);
        return span;
      }
      const a = document.createElement("a");
      a.href = url;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      applyStyle(a, STYLE_LINK);
      parseInlineInto(document, label, a);
      return a;
    } },
  ];

  // Collect all pattern matches with positions.
  let matches = [];
  for (const pattern of patterns) {
    const re = new RegExp(pattern.re.source, pattern.re.flags.includes("g") ? pattern.re.flags : `${pattern.re.flags}g`);
    let m;
    while ((m = re.exec(text)) !== null) {
      matches.push({ index: m.index, end: m.index + m[0].length, match: m, handler: pattern.handler });
    }
  }
  matches.sort((a, b) => a.index - b.index);

  // Remove overlapping matches (earliest start wins, shorter match dropped on tie).
  const filtered = [];
  for (const item of matches) {
    if (filtered.length === 0 || item.index >= filtered[filtered.length - 1].end) {
      filtered.push(item);
    }
  }

  let cursor = 0;
  for (const item of filtered) {
    if (item.index > cursor) {
      nodes.push(createTextNode(document, text.slice(cursor, item.index)));
    }
    nodes.push(item.handler(item.match));
    cursor = item.end;
  }
  if (cursor < text.length) {
    nodes.push(createTextNode(document, text.slice(cursor)));
  }

  return nodes;
}

function parseInlineInto(document, text, container) {
  const nodes = parseInline(document, text);
  for (const node of nodes) {
    container.appendChild(node);
  }
}

function parseBlockLines(document, lines) {
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Blank line -> separator
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Header
    const headerMatch = line.match(BLOCK_RE);
    if (headerMatch) {
      const level = headerMatch[1].length;
      const node = document.createElement(`h${level}`);
      applyStyle(node, {
        margin: "0 0 6px 0",
        fontWeight: "700",
        lineHeight: "1.3",
        color: "#edf2f7",
        fontSize: level === 1 ? "14px" : level === 2 ? "13px" : "12px",
      });
      parseInlineInto(document, headerMatch[2].trim(), node);
      blocks.push({ type: "header", node });
      i += 1;
      continue;
    }

    // Code fence
    const fenceMatch = line.match(CODE_FENCE_RE);
    if (fenceMatch) {
      const lang = fenceMatch[1];
      i += 1;
      const codeLines = [];
      while (i < lines.length && !lines[i].match(CODE_FENCE_RE)) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) {
        i += 1; // closing fence
      }
      const pre = document.createElement("pre");
      applyStyle(pre, {
        margin: "6px 0",
        padding: "8px",
        background: "#0d0f14",
        border: "1px solid #2d3340",
        borderRadius: "4px",
        overflow: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      });
      const code = document.createElement("code");
      applyStyle(code, {
        fontFamily: "monospace",
        fontSize: "11px",
        lineHeight: "1.4",
        color: "#d7f2e1",
        background: "transparent",
        border: "none",
        padding: "0",
      });
      if (lang) {
        code.dataset.language = lang;
      }
      setNodeText(document, code, codeLines.join("\n"));
      pre.appendChild(code);
      blocks.push({ type: "code", node: pre });
      continue;
    }

    // Unordered list
    const ulMatch = line.match(UL_RE);
    if (ulMatch) {
      const ul = document.createElement("ul");
      applyStyle(ul, {
        margin: "4px 0",
        paddingLeft: "18px",
        listStyleType: "disc",
      });
      while (i < lines.length) {
        const itemMatch = lines[i].match(UL_RE);
        if (!itemMatch) break;
        const li = document.createElement("li");
        applyStyle(li, { margin: "2px 0" });
        parseInlineInto(document, itemMatch[1], li);
        ul.appendChild(li);
        i += 1;
      }
      blocks.push({ type: "list", node: ul });
      continue;
    }

    // Ordered list
    const olMatch = line.match(OL_RE);
    if (olMatch) {
      const ol = document.createElement("ol");
      applyStyle(ol, {
        margin: "4px 0",
        paddingLeft: "20px",
        listStyleType: "decimal",
      });
      while (i < lines.length) {
        const itemMatch = lines[i].match(OL_RE);
        if (!itemMatch) break;
        const li = document.createElement("li");
        applyStyle(li, { margin: "2px 0" });
        parseInlineInto(document, itemMatch[2], li);
        ol.appendChild(li);
        i += 1;
      }
      blocks.push({ type: "list", node: ol });
      continue;
    }

    // Paragraph
    const paraLines = [];
    while (i < lines.length && lines[i].trim() !== "") {
      paraLines.push(lines[i]);
      i += 1;
    }
    const p = document.createElement("p");
    applyStyle(p, {
      margin: "0 0 6px 0",
      lineHeight: "1.4",
    });
    // Standard Markdown behaviour: collapse single newlines inside a paragraph
    // into spaces. Blank lines are the only paragraph separators.
    parseInlineInto(document, paraLines.join(" "), p);
    blocks.push({ type: "paragraph", node: p });
  }

  return blocks.map((b) => b.node);
}

/**
 * Render a markdown string into a DOM container.
 *
 * @param {Document} document
 * @param {string} text
 * @returns {HTMLElement} A <div> holding the parsed markdown content.
 */
export function renderMarkdown(document, text) {
  const container = document.createElement("div");
  container.className = "vibecomfy-markdown";

  if (typeof text !== "string" || text === "") {
    container.textContent = "";
    return container;
  }

  const lines = text.split("\n");
  const blockNodes = parseBlockLines(document, lines);
  for (let index = 0; index < blockNodes.length; index += 1) {
    const node = blockNodes[index];
    if (index === blockNodes.length - 1 && node?.style) {
      node.style.marginBottom = "0";
    }
    container.appendChild(node);
  }

  return container;
}

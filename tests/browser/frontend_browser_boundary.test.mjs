import test from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

async function javascriptFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return javascriptFiles(target);
    return entry.isFile() && entry.name.endsWith(".js") ? [target] : [];
  }));
  return nested.flat().sort();
}

function moduleSpecifiers(source) {
  const specifiers = [];
  const patterns = [
    /^[ \t]*(?:import|export)\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["'][ \t]*;?[ \t]*$/gm,
    /\bimport\s*\(\s*["']([^"']+)["']/g,
  ];
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) specifiers.push(match[1]);
  }
  return specifiers;
}

function browserCanResolve(specifier) {
  return specifier.startsWith("./")
    || specifier.startsWith("../")
    || specifier.startsWith("/")
    || specifier.startsWith("http://")
    || specifier.startsWith("https://")
    || specifier.startsWith("data:")
    || specifier.startsWith("blob:");
}

test("every shipped frontend module stays directly browser-resolvable", async () => {
  const violations = [];
  for (const filename of await javascriptFiles(WEB_ROOT)) {
    const source = await readFile(filename, "utf8");
    const relative = path.relative(REPO_ROOT, filename);
    for (const specifier of moduleSpecifiers(source)) {
      if (!browserCanResolve(specifier)) {
        violations.push(`${relative}: browser cannot resolve ${JSON.stringify(specifier)}`);
      }
    }
    if (/\brequire\s*\(/.test(source)) {
      violations.push(`${relative}: CommonJS require() is unavailable in the browser`);
    }
  }
  assert.deepEqual(violations, [], violations.join("\n"));
});

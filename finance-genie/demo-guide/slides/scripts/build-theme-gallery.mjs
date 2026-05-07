import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  mkdirSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";

const variants = {
  finance: {
    title: "Finance",
    file: "finance.html",
    theme: "finance",
    description: "Clean demo style with finance-oriented accenting.",
  },
  "graph-lakehouse": {
    title: "Graph Lakehouse",
    file: "graph-lakehouse.html",
    theme: "graph-lakehouse",
    description: "Technical graph-paper treatment for architecture and data model slides.",
  },
  default: {
    title: "Default",
    file: "default.html",
    theme: "default",
    description: "Built-in GitHub Markdown style.",
  },
  gaia: {
    title: "Gaia",
    file: "gaia.html",
    theme: "gaia",
    description: "Built-in classic presentation style.",
  },
  uncover: {
    title: "Uncover",
    file: "uncover.html",
    theme: "uncover",
    description: "Built-in centered minimal style.",
  },
};

const decks = {
  full: {
    title: "Full Demo Guide",
    source: "slides.md",
    description: "Complete graph-enriched lakehouse narrative.",
  },
  "15min": {
    title: "15-Minute Talk",
    source: "slides-15min.md",
    description: "Shorter version for tight conference or meeting slots.",
  },
};

const requested = process.argv[2] ?? "all";
const selected =
  requested === "all"
    ? Object.entries(variants)
    : [[requested, variants[requested]]].filter(([, variant]) => variant);

if (selected.length === 0) {
  console.error(`Unknown theme variant: ${requested}`);
  console.error(`Available variants: ${Object.keys(variants).join(", ")}, all`);
  process.exit(1);
}

rmSync("build", { force: true, recursive: true });
mkdirSync("build", { recursive: true });

for (const [deckKey, deck] of Object.entries(decks)) {
  for (const [variantKey, variant] of selected) {
    execFileSync(
      "marp",
      [
        deck.source,
        "-o",
        join("build", outputFile(deckKey, variantKey)),
        "--html",
        "--theme-set",
        "themes/finance.css",
        "--theme-set",
        "themes/graph-lakehouse.css",
        "--theme",
        variant.theme,
      ],
      { stdio: "inherit" },
    );
  }
}

for (const asset of readdirSync(".")) {
  if (/\.(png|jpe?g|gif|webp|svg)$/i.test(asset)) {
    copyFileSync(asset, join("build", asset));
  }
}

writeFileSync(join("build", ".nojekyll"), "");

if (requested === "all") {
  copyFileSync(join("build", outputFile("full", "finance")), join("build", "slides.html"));
  copyFileSync(join("build", outputFile("15min", "finance")), join("build", "slides-15min.html"));
  writeFileSync(join("build", "index.html"), renderIndex());
}

function outputFile(deckKey, variantKey) {
  if (deckKey === "full") {
    return variants[variantKey].file;
  }

  return `${deckKey}-${variantKey}.html`;
}

function renderIndex() {
  const sections = Object.entries(decks)
    .map(([deckKey, deck]) => {
      const cards = Object.entries(variants)
        .map(
          ([variantKey, variant]) => `
            <a class="card" href="./${outputFile(deckKey, variantKey)}">
              <span class="label">${escapeHtml(variant.title)}</span>
              <span class="description">${escapeHtml(variant.description)}</span>
            </a>`,
        )
        .join("");

      return `
        <section class="deck">
          <div class="deck-heading">
            <h2>${escapeHtml(deck.title)}</h2>
            <p>${escapeHtml(deck.description)}</p>
          </div>
          <div class="grid">
            ${cards}
          </div>
        </section>`;
    })
    .join("");

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Finance Genie Slides</title>
    <style>
      :root {
        color-scheme: light;
        --ink: #172033;
        --muted: #5b6678;
        --line: #d9e0ea;
        --accent: #0f766e;
        --accent-2: #2563eb;
        --surface: #ffffff;
        --bg: #f7fafc;
      }

      * {
        box-sizing: border-box;
      }

      body {
        background:
          linear-gradient(90deg, rgba(15, 118, 110, 0.08) 0 1px, transparent 1px),
          linear-gradient(rgba(37, 99, 235, 0.06) 0 1px, transparent 1px),
          var(--bg);
        background-size: 32px 32px;
        color: var(--ink);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0;
      }

      main {
        margin: 0 auto;
        max-width: 1080px;
        padding: 64px 24px;
      }

      h1 {
        font-size: clamp(36px, 6vw, 64px);
        line-height: 1;
        margin: 0 0 16px;
      }

      p {
        color: var(--muted);
        font-size: 19px;
        line-height: 1.5;
        margin: 0;
        max-width: 760px;
      }

      h2 {
        font-size: 28px;
        line-height: 1.1;
        margin: 0 0 8px;
      }

      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin: 32px 0 40px;
      }

      .button {
        align-items: center;
        background: var(--accent);
        border-radius: 6px;
        color: white;
        display: inline-flex;
        font-weight: 700;
        min-height: 44px;
        padding: 0 16px;
        text-decoration: none;
      }

      .button.secondary {
        background: var(--ink);
      }

      .deck {
        border-top: 1px solid var(--line);
        padding: 32px 0 0;
      }

      .deck + .deck {
        margin-top: 40px;
      }

      .deck-heading {
        margin-bottom: 18px;
      }

      .grid {
        display: grid;
        gap: 16px;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }

      .card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        color: inherit;
        display: flex;
        flex-direction: column;
        gap: 10px;
        min-height: 150px;
        padding: 20px;
        text-decoration: none;
      }

      .card:hover {
        border-color: var(--accent-2);
      }

      .label {
        font-size: 22px;
        font-weight: 800;
      }

      .description {
        color: var(--muted);
        font-size: 15px;
        line-height: 1.45;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>Finance Genie Slides</h1>
      <p>Choose a Marp theme variant. Each link opens the same deck rendered with a different built-in or custom theme.</p>
      <div class="actions">
        <a class="button" href="./slides.html">Open recommended deck</a>
        <a class="button secondary" href="./slides-15min.html">Open 15-minute deck</a>
      </div>
      ${sections}
    </main>
  </body>
</html>
`;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

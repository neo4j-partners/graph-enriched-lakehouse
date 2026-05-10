# Workshop Slides

Presentation-ready slides formatted for [Marp](https://marp.app/).

## Quick Start

Requires Node.js 22 LTS (`brew install node@22`) and a one-time `npm install` in this directory.

```bash
cd finance-genie/demo-guide/slides
npm install
npm run serve
```

Opens at http://localhost:8080/.

## Theme Variants

Build all theme variants into `build/`:

```bash
npm run build:all
```

This creates a clickable gallery at `build/index.html` for both `slides.md` and `slides-15min.md` with these variants:

- `finance.html`: custom finance/demo theme
- `graph-lakehouse.html`: custom graph-paper technical theme
- `default.html`: built-in Marp default theme
- `gaia.html`: built-in Marp Gaia theme
- `uncover.html`: built-in Marp Uncover theme

The 15-minute deck gets matching `15min-*.html` outputs, plus `slides-15min.html` as the recommended 15-minute build.

Build one variant at a time:

```bash
npm run build:finance
npm run build:graph
npm run build:gaia
```

The GitHub Pages workflow publishes the full gallery.

## Export to PDF

```bash
cd finance-genie/demo-guide/slides
npx marp slides.md --pdf --theme-set themes/finance.css --theme finance
```

## Troubleshooting

**`require is not defined in ES module scope` error?**
- Marp CLI is incompatible with Node.js 25+. Install Node 22 LTS: `brew install node@22`

**Images not showing?**
- Run `npm run build:all`; the build script copies local image assets into `build/`.

## Slide Format

Slides use Marp markdown format with pagination, syntax-highlighted code blocks, tables, and two-column layouts. See `slides.md` for the frontmatter template.

## Additional Resources

- [Marp Documentation](https://marpit.marp.app/)
- [Marp CLI Usage](https://github.com/marp-team/marp-cli)
- [Marp Themes](https://github.com/marp-team/marp-core/tree/main/themes)

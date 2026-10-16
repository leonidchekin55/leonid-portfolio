# Personal portfolio

Static portfolio and project demos. Main pages: `index.html` and `en.html`; project pages include `pulseboard.html`, `atlas-studio-demo.html`, and the Atelier and knowledge assistant pages. Legal pages are available in Russian and English.

## Local preview

Install Node.js 24.21.0 and Python 3, then run:

```sh
npm ci
npx playwright install chromium
python3 -m http.server 4173 --bind 127.0.0.1
```

Open <http://127.0.0.1:4173>. Stop the local server with Ctrl+C.

## Checks

```sh
npm test
```

This validates every root HTML page and local reference, checks the sitemap and runs a browser interaction against the local Atlas Studio demo. The browser demo uses local sample data and does not submit or publish anything.

When editing a page, keep its language, title, viewport metadata, accessible image alternatives, and linked local files in good shape. Review the changed page in the local preview before sharing changes.

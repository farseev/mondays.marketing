# mondays.marketing

Static site, no build step. Upload the folder contents to the web root of https://mondays.marketing/ (any static host: Netlify, Cloudflare Pages, Vercel, S3, nginx).

- Pages use relative links, so it also previews by opening index.html locally.
- Pretty URLs (/blog/<slug>/) resolve to index.html files; canonical tags, sitemap.xml and feed.xml use the https://mondays.marketing/ form.
- AI/answer-engine files: robots.txt (AI crawlers allowed), llms.txt, llms-full.txt, JSON-LD on every page (Organization, WebSite, FAQPage, BlogPosting, BreadcrumbList, Event).
- Set 404.html as the host's error page.
- Every CTA opens an email to ask@mondays.marketing: make sure that mailbox exists. The one exception is /plugin/ (below).
- /plugin/ is the free plugin download. Its form posts each lead to SOMIN's existing inquiry form (HTMLPub classic ID 4b5L8LUvvHCq8R22Q3Lx42, the somin.ai "See the platform" pop-up), tagged `plugin_downloaded = yes` and `lead_source = Agentic plugin download — Marketing Mondays (mondays.marketing/plugin)`, then downloads `downloads/marketing-mondays.plugin`. GA4 gets `generate_lead` (method `plugin_download_form`) and `file_download`.
- /sessions/the-2027-marketing-team/ is the 12 Oct 2026 talk as a self-contained deck (one HTML file, about 5 MB, presenter notes removed). It adds a slim site bar with home, previous/next and the plugin link; keys ← → move, f is fullscreen. The home hero links it as the latest session.
- To ship a new plugin version, replace `downloads/marketing-mondays.plugin` and `downloads/marketing-mondays.zip` (same zip, two names) and update the size shown under the form button in plugin/index.html. robots.txt keeps /downloads/ out of search results.
- Brand guidelines: /brand/ (page) and brand/BRAND-GUIDELINES.md.

## Languages (tools/i18n.py)

English pages are the source. `tools/i18n.py` (standard-library Python, shared by all SOMIN Group sites) renders
each English page as `/<code>/<path>/` for zh-hans, zh-hant, ja, ko, th, vi, id, ms, hi, fil, es, fr, de, pt,
ar (RTL) and ru once **all** of that page's text is translated. `brand/` and `sessions/` (slide replay) stay English-only (see `i18n/config.json`).

```
python3 tools/i18n.py status                 # coverage per language
python3 tools/i18n.py todo ja                # untranslated segments:  id<TAB>English
python3 tools/i18n.py merge ja ja.tsv        # id<TAB>translation lines; keep <g1>…</g1> / <x1/> placeholders
python3 tools/i18n.py build                  # language pages, hreflang, switcher, sitemaps, llms.txt
python3 tools/check_site.py                  # must end with 0 errors
```

Translations live in `i18n/<code>.json` (keyed by a hash of the English text, so edited English text shows up
as new work). Language pages get translated title/description/body/FAQ/JSON-LD/OG text, `<html lang>`
(+ `dir="rtl"` for Arabic), a self-canonical, the hreflang cluster + x-default, and the header language
switcher (GA4 event `language_switch`); the GA4 tag and lead tracking are copied unchanged. `sitemap.xml` is an
index of `sitemap-en.xml` and `sitemap-<code>.xml`. Never edit files under `/<code>/` by hand: the build rewrites them.

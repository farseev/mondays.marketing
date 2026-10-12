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

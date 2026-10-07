# mondays.marketing

Static site, no build step. Upload the folder contents to the web root of https://mondays.marketing/ (any static host: Netlify, Cloudflare Pages, Vercel, S3, nginx).

- Pages use relative links, so it also previews by opening index.html locally.
- Pretty URLs (/blog/<slug>/) resolve to index.html files; canonical tags, sitemap.xml and feed.xml use the https://mondays.marketing/ form.
- AI/answer-engine files: robots.txt (AI crawlers allowed), llms.txt, llms-full.txt, JSON-LD on every page (Organization, WebSite, FAQPage, BlogPosting, BreadcrumbList, Event).
- Set 404.html as the host's error page.
- Every CTA opens an email to ask@mondays.marketing: make sure that mailbox exists.
- Brand guidelines: /brand/ (page) and brand/BRAND-GUIDELINES.md.

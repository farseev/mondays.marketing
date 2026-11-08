#!/usr/bin/env python3
"""Site checker for the SOMIN Group static sites (stdlib only):  python3 tools/check_site.py
Checks every *.html page in the repo:
  - exactly one <h1>
  - every JSON-LD block parses; a FAQPage has as many questions as the page has <summary> elements
  - canonical present, absolute and self-referencing (404.html exempt)
  - hreflang (when present): every target exists, the cluster includes self and x-default, <html lang>
    matches the page's own entry, and the cluster is identical (reciprocal) on every page it lists
  - dir="rtl" on Arabic pages
  - every internal href/src resolves to a file (and #anchors to an id on the target page)
  - sitemap.xml and every sitemap-*.xml parse as XML and every <loc> exists on disk
Exit code 1 on any error.
"""
import html, json, os, re, sys, glob
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = open(os.path.join(ROOT, "CNAME"), encoding="utf-8").read().strip().split()[0]
SITE = "https://" + HOST
_cfg = os.path.join(ROOT, "i18n", "config.json")
CHECK_SKIP = json.load(open(_cfg, encoding="utf-8")).get("check_skip", []) if os.path.exists(_cfg) else []
errors = []


def err(page, msg):
    errors.append("%s: %s" % (os.path.relpath(page, ROOT), msg))


def url_to_file(url):
    p = urlsplit(url)
    if p.netloc and p.netloc != HOST:
        return None
    path = unquote(p.path)
    f = os.path.join(ROOT, path.lstrip("/"))
    if path.endswith("/") or path == "":
        f = os.path.join(f, "index.html")
    return f


def file_to_url(f):
    rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return SITE + "/" + rel


ids_cache = {}


def ids_of(f):
    if f not in ids_cache:
        try:
            ids_cache[f] = set(re.findall(r'\sid="([^"]+)"', open(f, encoding="utf-8").read()))
        except OSError:
            ids_cache[f] = set()
    return ids_cache[f]


def main():
    pages = [p for p in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True)
             if "/.git/" not in p and "/tools/" not in p and "/i18n/" not in p
             and not any(os.path.relpath(p, ROOT).replace(os.sep, "/").startswith(x) for x in CHECK_SKIP)]
    clusters = {}
    for f in sorted(pages):
        h = open(f, encoding="utf-8").read()
        is404 = os.path.basename(f) == "404.html"
        n = len(re.findall(r"<h1[\s>]", h))
        if n != 1:
            err(f, "%d <h1> elements" % n)
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try:
                d = json.loads(m.group(1))
            except ValueError as e:
                err(f, "JSON-LD does not parse: %s" % e)
                continue
            nodes = d.get("@graph", [d]) if isinstance(d, dict) else d
            for node in nodes if isinstance(nodes, list) else []:
                if isinstance(node, dict) and node.get("@type") == "FAQPage":
                    shown = {" ".join(html.unescape(re.sub(r"<[^>]+>", "", x)).split())
                             for x in re.findall(r"<summary[^>]*>(.*?)</summary>", h, re.S)}
                    for q in node.get("mainEntity", []):
                        if " ".join(q.get("name", "").split()) not in shown:
                            err(f, "FAQPage question not shown on the page: %s" % q.get("name", "")[:60])
        lang = re.search(r'<html lang="([^"]+)"', h)
        lang = lang.group(1) if lang else None
        if lang and lang.startswith("ar") and 'dir="rtl"' not in h[:400]:
            err(f, 'Arabic page without dir="rtl"')
        if not is404:
            c = re.search(r'<link rel="canonical" href="([^"]+)"', h)
            if not c:
                err(f, "no canonical")
            elif c.group(1) != file_to_url(f):
                err(f, "canonical %s is not self (%s)" % (c.group(1), file_to_url(f)))
            alts = re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', h)
            if alts:
                codes = dict(alts)
                if "x-default" not in codes:
                    err(f, "no x-default hreflang")
                if file_to_url(f) not in codes.values():
                    err(f, "hreflang cluster does not include self")
                elif lang and codes.get(lang) != file_to_url(f):
                    err(f, "html lang %s does not match own hreflang entry" % lang)
                for code, u in alts:
                    t = url_to_file(u)
                    if not t or not os.path.exists(t):
                        err(f, "hreflang %s -> missing %s" % (code, u))
                clusters[file_to_url(f)] = tuple(sorted(alts))
            elif re.search(r'^/?[a-z]{2,3}(?:-[a-z]{4})?/', os.path.relpath(f, ROOT)) and "/" in os.path.relpath(f, ROOT) \
                    and os.path.relpath(f, ROOT).split("/")[0] in ("zh-hans", "zh-hant", "ja", "ko", "th", "vi", "id", "ms", "hi",
                                                                 "fil", "es", "fr", "de", "pt", "ar", "ru"):
                err(f, "language page without hreflang")
        body = re.sub(r"<script(?![^>]*application/ld\+json)[^>]*>.*?</script>", "", h, flags=re.S)
        for attr, u in re.findall(r'\s(href|src)="([^"]+)"', body):
            u = html.unescape(u)
            if re.match(r"^(https?:|mailto:|tel:|data:|//|javascript:)", u):
                if u.startswith(SITE + "/"):
                    t = url_to_file(u)
                    if t and not os.path.exists(t):
                        err(f, "absolute link to missing %s" % u)
                continue
            path, _, frag = u.partition("#")
            path = path.split("?", 1)[0]
            if path == "":
                tgt = f
            elif path.startswith("/"):
                tgt = os.path.join(ROOT, unquote(path).lstrip("/"))
                if path.endswith("/") or os.path.isdir(tgt):
                    tgt = os.path.join(tgt, "index.html")
            else:
                tgt = os.path.normpath(os.path.join(os.path.dirname(f), unquote(path)))
                if path.endswith("/") or os.path.isdir(tgt):
                    tgt = os.path.join(tgt, "index.html")
            if not os.path.exists(tgt):
                err(f, "broken link %s" % u)
            elif frag and tgt.endswith(".html") and frag not in ids_of(tgt):
                err(f, "missing anchor #%s in %s" % (frag, os.path.relpath(tgt, ROOT)))
    for url, cl in clusters.items():
        for code, u in cl:
            if code == "x-default":
                continue
            other = clusters.get(u)
            if other is None or other != cl:
                err(url_to_file(url), "hreflang cluster differs from %s" % u)
                break
    for sm in glob.glob(os.path.join(ROOT, "sitemap*.xml")):
        try:
            t = ET.parse(sm)
        except ET.ParseError as e:
            err(sm, "XML does not parse: %s" % e)
            continue
        for loc in t.getroot().iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            tf = url_to_file(loc.text.strip())
            if not tf or not os.path.exists(tf):
                err(sm, "loc missing on disk: %s" % loc.text)
    for e in errors:
        print("ERROR", e)
    print("%d pages checked, %d errors" % (len(pages), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

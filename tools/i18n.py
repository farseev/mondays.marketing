#!/usr/bin/env python3
"""Multilingual build for the SOMIN Group static sites (standard library only).

One shared tool for mondays.marketing, somonitor.ai, mindfuse.sg, snmrush.com, gpt5.marketing,
gpt3.marketing, agentc.marketing and fmedia.marketing. The site is read from the repo (CNAME, the
English pages, assets/site.css); per-site options live in i18n/config.json.

English pages at the site root are the source text and the template for every language. Every
translatable piece of text (visible text runs, alt/title/aria-label/placeholder attributes, the meta
description, OG/Twitter text, JSON-LD text) is a *segment*, keyed by a hash of its English text.
Translations live in i18n/<code>.json ({id: text}); i18n/source.json holds the English.

Commands
  python3 tools/i18n.py extract                 refresh i18n/source.json + i18n/pages.json
  python3 tools/i18n.py todo <code> [path ...]  print untranslated segments as  id<TAB>English
  python3 tools/i18n.py merge <code> <file>     merge  id<TAB>translation  lines (placeholders checked)
  python3 tools/i18n.py build [--prune]         render every page that is 100% translated as /<code>/...,
                                                hreflang clusters, language switcher, sitemaps, llms.txt
  python3 tools/i18n.py status                  coverage per language

Inline markup inside a segment appears as <g1>...</g1> (paired tags) and <x1/> (void tags); keep them.
A page goes live in a language only when ALL its segments are translated, and a language goes live
only when its home page is complete. English files are never re-serialised: the build only adds the
hreflang cluster, og:locale alternates and the language switcher to them.
"""
import datetime, glob, hashlib, html, json, os, posixpath, re, sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(ROOT, "i18n")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


HOST = read(os.path.join(ROOT, "CNAME")).strip().split()[0]
SITE = "https://" + HOST
CFG = json.loads(read(os.path.join(I18N, "config.json"))) if os.path.exists(os.path.join(I18N, "config.json")) else {}
EXCLUDE = CFG.get("exclude", ["brand/"])           # page prefixes that stay English-only (not translated)
SKIP_CLASSES = set(CFG.get("skip_classes", []))     # elements whose text is never translated (e.g. client logo lists)
GROUP_TERMS = ["SOMIN", "SOMONITOR", "MindFuse", "SNMRush", "FMedia", "AgentC", "GPT3 Marketing", "GPT5 Marketing",
               "Marketing Mondays", "SEO", "AEO", "GEO", "ROAS", "SO MIN", "SOMIN.ai",
               # client and platform names that appear on their own (logo lists, case-study cards)
               "Pepsi", "Fujifilm", "Land Rover Defender", "Defender", "Havas Media", "SAMY", "Analytic Partners",
               "Mothercare", "SM Universe", "Keeta", "Senoko Energy", "Reassured", "KPI Media", "NEO360", "Blak Labs",
               "Vamp", "Miraflora", "VIVA", "ExoStride", "Figma", "Postly", "Claude", "Claude Code", "ChatGPT",
               "Gemini", "Perplexity", "LinkedIn", "YouTube", "WhatsApp", "RSS", "Block71", "Grab", "Hasbro"]
KEEP_TERMS = {t.lower() for t in GROUP_TERMS + CFG.get("keep", [])}

# code, html lang/hreflang, og:locale, native name, short label, "Language" label, Noto fallback font
LANGS = [
    ("en", None, None, "English", "EN", "Language", None),
    ("zh-hans", "zh-Hans", "zh_CN", "简体中文", "简中", "语言", "Noto Sans SC"),
    ("zh-hant", "zh-Hant", "zh_TW", "繁體中文", "繁中", "語言", "Noto Sans TC"),
    ("ja", "ja", "ja_JP", "日本語", "日本語", "言語", "Noto Sans JP"),
    ("ko", "ko", "ko_KR", "한국어", "한국어", "언어", "Noto Sans KR"),
    ("th", "th", "th_TH", "ไทย", "ไทย", "ภาษา", "Noto Sans Thai"),
    ("vi", "vi", "vi_VN", "Tiếng Việt", "VI", "Ngôn ngữ", "Noto Sans"),
    ("id", "id", "id_ID", "Bahasa Indonesia", "ID", "Bahasa", None),
    ("ms", "ms", "ms_MY", "Bahasa Melayu", "MS", "Bahasa", None),
    ("hi", "hi", "hi_IN", "हिन्दी", "हिन्दी", "भाषा", "Noto Sans Devanagari"),
    ("fil", "fil", "tl_PH", "Filipino", "FIL", "Wika", None),
    ("es", "es", "es_ES", "Español", "ES", "Idioma", None),
    ("fr", "fr", "fr_FR", "Français", "FR", "Langue", None),
    ("de", "de", "de_DE", "Deutsch", "DE", "Sprache", None),
    ("pt", "pt", "pt_BR", "Português", "PT", "Idioma", None),
    ("ar", "ar", "ar_AR", "العربية", "عربي", "اللغة", "Noto Sans Arabic"),
    ("ru", "ru", "ru_RU", "Русский", "RU", "Язык", "Noto Sans"),
]
L = {l[0]: dict(code=l[0], tag=l[1], og=l[2], name=l[3], short=l[4], label=l[5], font=l[6]) for l in LANGS}
CODES = [l[0] for l in LANGS]

INLINE = {"a", "abbr", "b", "br", "code", "em", "i", "mark", "q", "s", "small", "span", "strong", "sub", "sup",
          "time", "u", "wbr", "img"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "param"}
SKIP = {"script", "style", "svg", "noscript", "template"}
ATTRS = ("alt", "title", "aria-label", "placeholder")
META_NAMES = {"description", "twitter:title", "twitter:description", "twitter:image:alt"}
META_PROPS = {"og:title", "og:description", "og:image:alt", "article:section"}
LD_TEXT_KEYS = {"name", "headline", "description", "abstract", "text", "articleSection", "caption",
                "slogan", "disambiguatingDescription", "alternativeHeadline"}
LD_SKIP_TYPES = {"Organization", "WebSite", "Person", "Brand"}
URLISH_RE = re.compile(r"^(?:https?://\S+|www\.\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|[\w-]+(?:\.[\w-]+)*\.(?:ai|com|sg|marketing|io|org|net|txt|xml|json)(?:/\S*)?)$", re.I)
NUM_RE = re.compile(r"^[\d\s.,:;+×x–—\-−%°~<>/()·|#&!?]*$")
PH_RE = re.compile(r"</?g\d+>|<x\d+/>")
SW_START, SW_END = "<!--i18n:langsw-->", "<!--/i18n:langsw-->"
CSS_START, CSS_END = "/* i18n:start (tools/i18n.py) */", "/* i18n:end */"


def sid(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def norm(s):
    return re.sub(r"[ \t\n\r\f\v]+", " ", s).strip(" \t\n\r\f\v")


def translatable(t):
    if not t or not re.search(r"[^\W\d_]", t) or NUM_RE.match(t) or URLISH_RE.match(t.strip()):
        return False
    core = re.sub(r"[\s.,:;!?·|/()\-–—→←]+", " ", t).strip().lower()
    return core not in KEEP_TERMS and core.replace(" ", "") not in KEEP_TERMS


def en_tag():
    m = re.search(r'<html lang="([^"]+)"', read(os.path.join(ROOT, "index.html")))
    return m.group(1) if m else "en"


def en_og():
    m = re.search(r'<meta property="og:locale" content="([^"]+)"', read(os.path.join(ROOT, "index.html")))
    return m.group(1) if m else "en_US"


L["en"]["tag"], L["en"]["og"] = en_tag(), en_og()


# ---------------------------------------------------------------- parsing
class Tok:
    __slots__ = ("kind", "tag", "attrs", "start", "end", "raw", "el")

    def __init__(self, kind, tag, attrs, start):
        self.kind, self.tag, self.attrs, self.start, self.end, self.raw, self.el = kind, tag, attrs, start, None, None, None


class El:
    __slots__ = ("tag", "attrs", "open", "close", "children", "parent")

    def __init__(self, tag, attrs, open_i, parent):
        self.tag, self.attrs, self.open, self.close, self.children, self.parent = tag, dict(attrs), open_i, None, [], parent


class Parser(HTMLParser):
    def __init__(self, doc):
        super().__init__(convert_charrefs=False)
        self.lines = [0] + [m.end() for m in re.finditer("\n", doc)]
        self.toks = []

    def off(self):
        ln, col = self.getpos()
        return self.lines[ln - 1] + col

    def add(self, kind, tag=None, attrs=()):
        self.toks.append(Tok(kind, tag, attrs, self.off()))

    def handle_starttag(self, tag, attrs): self.add("start", tag, attrs)
    def handle_startendtag(self, tag, attrs): self.add("startend", tag, attrs)
    def handle_endtag(self, tag): self.add("end", tag)
    def handle_data(self, d): self.add("data")
    def handle_entityref(self, n): self.add("data")
    def handle_charref(self, n): self.add("data")
    def handle_comment(self, d): self.add("other")
    def handle_decl(self, d): self.add("other")
    def handle_pi(self, d): self.add("other")
    def unknown_decl(self, d): self.add("other")


def parse(doc):
    p = Parser(doc)
    p.feed(doc)
    p.close()
    toks = p.toks
    for i, t in enumerate(toks):
        t.end = toks[i + 1].start if i + 1 < len(toks) else len(doc)
        t.raw = doc[t.start:t.end]
    root = El("#root", (), -1, None)
    cur = root
    for i, t in enumerate(toks):
        if t.kind in ("start", "startend"):
            el = El(t.tag, t.attrs, i, cur)
            t.el = el
            cur.children.append(("el", el))
            if t.kind == "start" and t.tag not in VOID:
                cur = el
            else:
                el.close = i
        elif t.kind == "end":
            x = cur
            while x is not root and x.tag != t.tag:
                x = x.parent
            if x is not root:
                x.close = i
                cur = x.parent
        elif t.kind == "data":
            cur.children.append(("tok", i))
    return toks, root


# ---------------------------------------------------------------- segmentation
class Seg:
    __slots__ = ("kind", "text", "id", "a", "b", "tags", "lead", "trail", "tok", "attr")


def text_of_children(toks, children, tagmap):
    out = []

    def ser(kind, x):
        if kind == "tok":
            out.append(html.unescape(toks[x].raw))
        else:
            n = len(tagmap) + 1
            if x.close is None or x.close == x.open or x.tag in VOID:
                tagmap.append(("x", x.open, None))
                out.append("<x%d/>" % n)
            else:
                tagmap.append(("g", x.open, x.close))
                out.append("<g%d>" % n)
                for c in x.children:
                    ser(*c)
                out.append("</g%d>" % n)
    for c in children:
        ser(*c)
    return "".join(out)


def skipped(el):
    if el.tag in SKIP or el.attrs.get("translate") == "no":
        return True
    cls = set((el.attrs.get("class") or "").split())
    return bool(cls & SKIP_CLASSES)


def segments(doc):
    toks, root = parse(doc)
    segs = []

    def is_inline(c):
        return c[0] == "tok" or (c[1].tag in INLINE and not skipped(c[1]))

    def visit(el):
        if el is not root and skipped(el):
            return
        runs, run = [], []
        for c in el.children:
            if is_inline(c):
                run.append(c)
            else:
                if run:
                    runs.append(("run", run)); run = []
                runs.append(("blk", c))
        if run:
            runs.append(("run", run))
        for kind, r in runs:
            if kind == "blk":
                if r[0] == "el":
                    visit(r[1])
                continue
            if any(k == "tok" and toks[x].raw.strip() for k, x in r):
                make_run_seg(r)
            else:
                for k, x in r:
                    if k == "el":
                        visit(x)

    def first_tok(c):
        return c[1] if c[0] == "tok" else c[1].open

    def last_tok(c):
        return c[1] if c[0] == "tok" else (c[1].close if c[1].close is not None else c[1].open)

    def make_run_seg(r):
        while r and r[0][0] == "tok" and not toks[r[0][1]].raw.strip():
            r = r[1:]
        while r and r[-1][0] == "tok" and not toks[r[-1][1]].raw.strip():
            r = r[:-1]
        if not r:
            return
        tagmap = []
        raw_text = text_of_children(toks, r, tagmap)
        a, b = toks[first_tok(r[0])].start, toks[last_tok(r[-1])].end
        s = Seg()
        s.kind, s.a, s.b, s.tags, s.tok, s.attr = "run", a, b, tagmap, None, None
        s.lead = re.match(r"\s*", doc[a:b]).group(0)
        s.trail = re.search(r"\s*$", doc[a:b]).group(0)
        s.text = norm(raw_text)
        s.id = sid(s.text) if translatable(PH_RE.sub("", s.text)) else None
        segs.append(s)

    visit(root)
    for i, t in enumerate(toks):
        if t.kind not in ("start", "startend") or t.tag in ("script", "style"):
            continue
        at = dict(t.attrs)
        names = [a for a in ATTRS if at.get(a)]
        if t.tag == "meta" and at.get("content") and (at.get("name") in META_NAMES or at.get("property") in META_PROPS):
            names.append("content")
        for a in names:
            s = Seg()
            s.kind, s.tok, s.attr, s.tags, s.lead, s.trail, s.a, s.b = "attr", i, a, [], "", "", None, None
            s.text = norm(at[a])
            s.id = sid(s.text) if translatable(s.text) else None
            segs.append(s)
    for i, t in enumerate(toks):
        if t.kind == "start" and t.tag == "script" and dict(t.attrs).get("type") == "application/ld+json":
            for val in ld_texts(json.loads(toks[i + 1].raw)):
                s = Seg()
                s.kind, s.tok, s.attr, s.tags, s.lead, s.trail, s.a, s.b = "ld", i + 1, None, [], "", "", None, None
                s.text = val
                s.id = sid(val) if translatable(val) else None
                segs.append(s)
    return toks, segs


def ld_skip(d):
    t = d.get("@type")
    t = t if isinstance(t, list) else [t]
    return any(x in LD_SKIP_TYPES for x in t)


def ld_texts(d, skip=False):
    out = []
    if isinstance(d, dict):
        skip = skip or ld_skip(d)
        for k, v in d.items():
            if isinstance(v, str):
                if not skip and k in LD_TEXT_KEYS:
                    out.append(norm(v))
            else:
                out += ld_texts(v, skip)
    elif isinstance(d, list):
        for v in d:
            out += ld_texts(v, skip)
    return out


# ---------------------------------------------------------------- pages and paths
def en_pages():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True)):
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        top = rel.split("/")[0]
        if top in (".git", "tools", "i18n") or top in L or any(rel.startswith(x) for x in EXCLUDE):
            continue
        out.append(rel)
    return sorted(out, key=lambda r: (r != "index.html", r.count("/"), r))


def page_path(rel):
    return "/" + rel[: -len("index.html")]


def lang_path(code, path):
    return path if code == "en" else "/" + code + path


def load_tm(code):
    p = os.path.join(I18N, code + ".json")
    return json.loads(read(p)) if os.path.exists(p) else {}


def save_tm(code, tm):
    write(os.path.join(I18N, code + ".json"), json.dumps(dict(sorted(tm.items())), ensure_ascii=False, indent=0) + "\n")


def is_page_dir(path):
    return os.path.exists(os.path.join(ROOT, path.lstrip("/"), "index.html"))


def rel_url(from_dir, target):
    r = posixpath.relpath(target, from_dir)
    return r


def rewrite_link(v, en_dir, out_dir, ctx):
    """Relative href/src on EN page in en_dir -> equivalent relative link from out_dir (language page)."""
    if not v or re.match(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#)", v):
        return v
    path, q, frag = v, "", ""
    if "#" in path:
        path, frag = path.split("#", 1); frag = "#" + frag
    if "?" in path:
        path, q = path.split("?", 1); q = "?" + q
    if path == "":
        return v
    absp = posixpath.normpath(posixpath.join(en_dir, path))
    keep_file = False
    if absp.endswith("/index.html"):
        d, keep_file = absp[: -len("index.html")], True
    elif path.endswith("/") or path in (".", "..") or path.endswith("/.."):
        d = absp.rstrip("/") + "/"
    elif is_page_dir(absp + "/"):
        d = absp + "/"
    else:
        r = rel_url(out_dir, absp)
        return r + q + frag
    tgt = ctx.map_page(d)
    r = rel_url(out_dir, tgt)
    if keep_file:
        r = "index.html" if r == "." else r + "/index.html"
    else:
        r = "./" if r == "." else r + "/"
    return r + q + frag


class Ctx:
    def __init__(self, code, avail):
        self.code, self.avail = code, avail

    def map_page(self, path):
        if self.code != "en" and path in self.avail:
            return lang_path(self.code, path)
        return path

    def map_url(self, url):
        if not url.startswith(SITE + "/"):
            return url
        path, _, frag = url[len(SITE):].partition("#")
        if path == "/" and frag:          # shared entity ids (#org, #site ...)
            return url
        if not path.endswith("/"):
            return url
        return SITE + self.map_page(path) + (("#" + frag) if frag else "")


# ---------------------------------------------------------------- rendering
def esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\xa0", "&nbsp;")


def rebuild_tag(tok, new_attrs):
    raw = tok.raw
    for name, val in new_attrs.items():
        pat = re.compile(r'(\s%s=")([^"]*)(")' % re.escape(name))
        raw = pat.sub(lambda m: m.group(1) + val + m.group(3), raw, count=1)
    return raw


def strip_switcher(doc):
    return re.sub(re.escape(SW_START) + ".*?" + re.escape(SW_END), SW_START + SW_END, doc, flags=re.S)


def ensure_switcher_slot(doc):
    if SW_START in doc:
        return strip_switcher(doc)
    m = re.search(r'<nav aria-label="Main">.*?(</nav>)', doc, re.S)
    if not m:
        return doc
    return doc[: m.start(1)] + SW_START + SW_END + doc[m.start(1):]


def render(doc, en_rel, code, tm, avail, clusters, shipped):
    """Return (html, missing_ids). doc is the EN page with an empty switcher slot."""
    en_path = page_path(en_rel)
    out_path = lang_path(code, en_path)
    missing = set()
    if code == "en":
        out = doc
    else:
        ctx = Ctx(code, avail)
        toks, segs = segments(doc)

        def tr(seg):
            if seg.id is None:
                return seg.text
            v = tm.get(seg.id)
            if v is None:
                missing.add(seg.id)
                return seg.text
            return v

        newtag, attr_tr = {}, {}
        for s in segs:
            if s.kind == "attr":
                attr_tr.setdefault(s.tok, {})[s.attr] = tr(s)
        for i, t in enumerate(toks):
            if t.kind not in ("start", "startend"):
                continue
            at = dict(t.attrs)
            repl = {a: html.escape(v, quote=True) for a, v in attr_tr.get(i, {}).items()}
            for a in ("href", "src"):
                v = at.get(a)
                if v is None:
                    continue
                nv = rewrite_link(v, en_path, out_path, ctx)
                if nv != v:
                    repl[a] = html.escape(nv, quote=True)
            newtag[i] = rebuild_tag(t, repl) if repl else t.raw
        edits, covered = [], []
        for s in segs:
            if s.kind != "run":
                continue
            txt, pieces, pos = tr(s), [], 0
            for m in PH_RE.finditer(txt):
                pieces.append(esc_text(txt[pos:m.start()]))
                ph = m.group(0)
                kind, o, c = s.tags[int(re.search(r"\d+", ph).group(0)) - 1]
                pieces.append(toks[c].raw if ph.startswith("</") else newtag.get(o, toks[o].raw))
                pos = m.end()
            pieces.append(esc_text(txt[pos:]))
            edits.append((s.a, s.b, s.lead + "".join(pieces) + s.trail))
            covered.append((s.a, s.b))
        for i, t in enumerate(toks):
            if t.kind in ("start", "startend") and newtag[i] != t.raw and not any(a <= t.start < b for a, b in covered):
                edits.append((t.start, t.end, newtag[i]))
        # relative paths inside inline scripts (e.g. a download URL '../downloads/x.zip')
        for i, t in enumerate(toks):
            if t.kind == "start" and t.tag == "script" and not dict(t.attrs).get("type") and i + 1 < len(toks) and toks[i + 1].kind == "data":
                js = toks[i + 1].raw
                nj = re.sub(r"""(['"])((?:\.\./|\./)[^'"\s]*)\1""",
                            lambda m: m.group(1) + rewrite_link(m.group(2), en_path, out_path, ctx) + m.group(1), js)
                if nj != js:
                    edits.append((toks[i + 1].start, toks[i + 1].end, nj))
        ld_map = {s.text: tr(s) for s in segs if s.kind == "ld"}
        for i, t in enumerate(toks):
            if t.kind == "start" and t.tag == "script" and dict(t.attrs).get("type") == "application/ld+json":
                d = ld_transform(json.loads(toks[i + 1].raw), ld_map, ctx, L[code]["tag"])
                js = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
                edits.append((toks[i + 1].start, toks[i + 1].end, js))
        edits.sort(key=lambda e: e[0])
        res, pos = [], 0
        for a, b, txt in edits:
            if a < pos:
                raise RuntimeError("overlapping edits in %s" % en_rel)
            res.append(doc[pos:a]); res.append(txt); pos = b
        res.append(doc[pos:])
        out = "".join(res)
    out = head_fixups(out, code, en_path, out_path, clusters.get(en_path, ["en"]))
    out = out.replace(SW_START + SW_END, SW_START + switcher(code, en_path, out_path, clusters, shipped) + SW_END)
    return out, missing


def ld_transform(d, ld_map, ctx, tag, skip=False):
    if isinstance(d, dict):
        skip2 = skip or ld_skip(d)
        o = {}
        for k, v in d.items():
            if isinstance(v, str):
                if skip2:
                    o[k] = v
                elif k == "inLanguage":
                    o[k] = tag
                elif k in LD_TEXT_KEYS:
                    o[k] = ld_map.get(norm(v), v)
                elif v.startswith(SITE + "/"):
                    o[k] = ctx.map_url(v)
                else:
                    o[k] = v
            else:
                o[k] = ld_transform(v, ld_map, ctx, tag, skip2)
        return o
    if isinstance(d, list):
        return [ld_transform(v, ld_map, ctx, tag, skip) for v in d]
    return d


def font_vars():
    css = read(os.path.join(ROOT, "assets", "site.css"))
    out = {}
    for var in ("--fh", "--fb"):
        m = re.search(r"%s:([^;}]+)" % var, css)
        if m:
            out[var] = m.group(1).strip()
    return out


def with_font(stack, fam):
    parts = [p.strip() for p in stack.split(",")]
    generic = {"system-ui", "sans-serif", "serif", "monospace", "-apple-system", "ui-sans-serif"}
    for i, p in enumerate(parts):
        if p.strip("'\"") in generic:
            parts.insert(i, "'%s'" % fam)
            break
    else:
        parts.append("'%s'" % fam)
    return ",".join(parts)


def head_fixups(doc, code, en_path, out_path, cluster):
    lg = L[code]
    url = SITE + out_path
    attrs = 'lang="%s"' % lg["tag"] + (' dir="rtl"' if code == "ar" else "")
    doc = re.sub(r'<html lang="[^"]*"(?: dir="rtl")?>', "<html %s>" % attrs, doc, count=1)
    doc = re.sub(r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="%s">' % url, doc, count=1)
    doc = re.sub(r'\n?<link rel="alternate" hreflang="[^"]*" href="[^"]*">', "", doc)
    if len(cluster) > 1:
        alts = "".join('\n<link rel="alternate" hreflang="%s" href="%s%s">' % (L[c]["tag"], SITE, lang_path(c, en_path)) for c in cluster)
        alts += '\n<link rel="alternate" hreflang="x-default" href="%s%s">' % (SITE, en_path)
        doc = re.sub(r'(<link rel="canonical" href="[^"]*">)', lambda m: m.group(1) + alts, doc, count=1)
    doc = re.sub(r'<meta property="og:url" content="[^"]*">', '<meta property="og:url" content="%s">' % url, doc, count=1)
    doc = re.sub(r'\n?<meta property="og:locale:alternate" content="[^"]*">', "", doc)
    others = "".join('\n<meta property="og:locale:alternate" content="%s">' % L[c]["og"] for c in cluster if c != code)
    doc = re.sub(r'<meta property="og:locale" content="[^"]*">', lambda m: '<meta property="og:locale" content="%s">%s' % (lg["og"], others), doc, count=1)
    doc = re.sub(r'\n?<style id="i18n-font">.*?</style>', "", doc, flags=re.S)
    if code != "en" and lg["font"]:
        fam = lg["font"]
        q = fam.replace(" ", "+") + ":wght@400;500;600;700"
        doc = re.sub(r'(<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2\?[^"]*?)(&display=swap")',
                     lambda m: m.group(1) + ("&amp;family=" if "&amp;" in m.group(1) else "&family=") + q + m.group(2), doc, count=1)
        fv = font_vars()
        if fv:
            style = '<style id="i18n-font">:root{%s}</style>' % ";".join("%s:%s" % (k, with_font(v, fam)) for k, v in fv.items())
            doc = re.sub(r'(<link rel="stylesheet" href="[^"]*assets/site\.css">)', lambda m: m.group(1) + "\n" + style, doc, count=1)
    return doc


SW_JS = ("<script>document.addEventListener('click',function(e){var a=e.target.closest('.langsw a[hreflang]');"
         "if(a&&typeof gtag==='function')gtag('event','language_switch',{language_from:document.documentElement.lang,"
         "language_to:a.getAttribute('hreflang'),page_path:location.pathname});var d=document.querySelector('.langsw[open]');"
         "if(d&&!d.contains(e.target))d.removeAttribute('open');});</script>")


def switcher(code, en_path, out_path, clusters, shipped):
    if len(shipped) < 2:
        return ""
    have = clusters.get(en_path, ["en"])
    lis = []
    for c in shipped:
        tgt = lang_path(c, en_path) if c in have else lang_path(c, "/")
        r = rel_url(out_path, tgt)
        r = "index.html" if r == "." else r + "/index.html"
        cur = ' aria-current="page"' if c == code else ""
        lis.append('<li><a href="%s" hreflang="%s" lang="%s"%s>%s</a></li>' % (r, L[c]["tag"], L[c]["tag"], cur, L[c]["name"]))
    return ('<details class="langsw" translate="no"><summary aria-label="%s: %s"><span>%s</span></summary><ul>%s</ul></details>%s'
            % (L[code]["label"], L[code]["name"], L[code]["short"], "".join(lis), SW_JS))


SW_CSS = CSS_START + """
.langsw{position:relative;font:500 14px/1 var(--fb,system-ui,sans-serif)}
.langsw summary{font:500 14px/1 var(--fb,system-ui,sans-serif);justify-content:flex-start;list-style:none;cursor:pointer;display:flex;align-items:center;gap:6px;padding:9px 12px;border-radius:999px;color:var(--ink,#111);box-shadow:inset 0 0 0 1px var(--line,rgba(0,0,0,.2));white-space:nowrap}
.langsw summary::-webkit-details-marker{display:none}
.langsw summary::before{content:"";width:15px;height:15px;flex:none;background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18'/%3E%3C/svg%3E") center/contain no-repeat}
.langsw summary:focus-visible{outline:2px solid var(--atext,currentColor);outline-offset:2px}
.langsw ul{position:absolute;right:0;top:calc(100% + 8px);z-index:30;margin:0;padding:6px;list-style:none;min-width:190px;max-height:70vh;overflow:auto;background:#fff;border:1px solid var(--line,#ddd);border-radius:10px;box-shadow:0 12px 32px rgba(0,0,0,.14)}
header.site nav .langsw ul a,.langsw ul a{display:block;padding:9px 12px;border-radius:6px;color:#1b1b1b;font-size:14px;font-weight:500;text-decoration:none;white-space:nowrap}
.langsw ul a:hover,.langsw ul a:focus-visible{background:rgba(0,0,0,.06)}
.langsw ul a[aria-current]{font-weight:700}
.langsw summary::after,details.langsw[open] summary::after{content:none;display:none}
details.langsw,details.langsw[open]{border:0;padding:0;margin:0}
[dir=rtl] .langsw ul{right:auto;left:0}
[dir=rtl] .skip{left:auto;right:-9999px}[dir=rtl] .skip:focus{right:12px}
:lang(ar) *,:lang(hi) *,:lang(th) *{letter-spacing:0!important}
@media(max-width:820px){.langsw summary{padding:8px 10px;font-size:13px}}
[dir=rtl] svg{direction:ltr}[dir=rtl] .hero::after{transform:scaleX(-1)}
@media(max-width:560px){header.site nav:has(.langsw){gap:8px;min-width:0}header.site nav:has(.langsw) .btn{display:none}.langsw summary{padding:8px;gap:0}.langsw summary span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
""" + CSS_END + "\n"


def ensure_css():
    p = os.path.join(ROOT, "assets", "site.css")
    css = read(p)
    new = re.sub(re.escape(CSS_START) + ".*?" + re.escape(CSS_END) + "\n?", "", css, flags=re.S)
    new = new.rstrip("\n") + "\n" + SW_CSS
    if new != css:
        write(p, new)


# ---------------------------------------------------------------- commands
def cmd_extract(quiet=False):
    src, pages = {}, {}
    for rel in en_pages():
        doc = strip_switcher(read(os.path.join(ROOT, rel)))
        _, segs = segments(doc)
        ids = []
        for s in segs:
            if s.id:
                src[s.id] = s.text
                if s.id not in ids:
                    ids.append(s.id)
        pages[page_path(rel)] = ids
    write(os.path.join(I18N, "source.json"), json.dumps(dict(sorted(src.items())), ensure_ascii=False, indent=0) + "\n")
    write(os.path.join(I18N, "pages.json"), json.dumps(pages, ensure_ascii=False, indent=0) + "\n")
    if not quiet:
        print("%d pages, %d unique segments, %d words" % (len(pages), len(src), sum(len(v.split()) for v in src.values())))
    return src, pages


def availability(code, pages, tm):
    if code == "en":
        return set(pages)
    if not all(i in tm for i in pages.get("/", [None])):
        return set()
    return {p for p, ids in pages.items() if all(i in tm for i in ids)}


def cmd_todo(code, which):
    src, pages = cmd_extract(quiet=True)
    tm = load_tm(code)
    seen = set()
    for path in (which or list(pages)):
        path = "/" + path.strip("/") + "/" if path.strip("/") else "/"
        for i in pages.get(path, []):
            if i not in tm and i not in seen:
                seen.add(i)
                print("%s\t%s" % (i, src[i]))


def check_ph(en, tr):
    return sorted(PH_RE.findall(en)) == sorted(PH_RE.findall(tr))


def cmd_merge(code, f):
    src, _ = cmd_extract(quiet=True)
    tm = load_tm(code)
    bad, n = 0, 0
    for ln in read(f).splitlines():
        if not ln.strip() or "\t" not in ln:
            continue
        i, t = ln.split("\t", 1)
        i, t = i.strip(), t.strip()
        if ":" in i:                       # group files: "<repo>:<id>"
            i = i.rsplit(":", 1)[1]
        if i not in src:
            print("unknown id", i); bad += 1; continue
        if not t or not check_ph(src[i], t):
            print("placeholder mismatch/empty", i, src[i][:60], "||", t[:60]); bad += 1; continue
        tm[i] = t; n += 1
    save_tm(code, tm)
    print("merged %d, rejected %d -> i18n/%s.json (%d entries)" % (n, bad, code, len(tm)))


def cmd_status():
    src, pages = cmd_extract(quiet=True)
    need = set(i for ids in pages.values() for i in ids)
    for code in CODES[1:]:
        tm = load_tm(code)
        av = availability(code, pages, tm)
        print("%-8s %4d/%4d segments  %2d/%2d pages live" % (code, len(need & set(tm)), len(need), len(av), len(pages)))


def cmd_build():
    src, pages = cmd_extract(quiet=True)
    ensure_css()
    tms = {c: load_tm(c) for c in CODES[1:]}
    avail = {"en": set(pages)}
    for c in CODES[1:]:
        avail[c] = availability(c, pages, tms[c])
    shipped = [c for c in CODES if avail[c]]
    clusters = {path: [c for c in CODES if path in avail[c]] for path in pages}
    written = []
    for rel in en_pages():
        en_path = page_path(rel)
        p = os.path.join(ROOT, rel)
        orig = read(p)
        base = ensure_switcher_slot(orig)
        for c in CODES:
            if en_path not in avail[c]:
                continue
            out, missing = render(base, rel, c, tms.get(c, {}), avail[c], clusters, shipped)
            if missing:
                raise RuntimeError("%s %s missing %d" % (c, en_path, len(missing)))
            dest = os.path.join(ROOT, lang_path(c, en_path).lstrip("/"), "index.html")
            if c == "en":
                if out != orig:
                    write(dest, out)
            else:
                write(dest, out)
            written.append(lang_path(c, en_path))
    stale = []
    for c in CODES[1:]:
        for f in glob.glob(os.path.join(ROOT, c, "**", "index.html"), recursive=True):
            rp = "/" + os.path.relpath(f, ROOT).replace(os.sep, "/")[: -len("index.html")]
            if rp not in written:
                if "--prune" in sys.argv:
                    os.remove(f)
                else:
                    stale.append(rp)
    if stale:
        sys.exit("refusing to drop %d existing language pages (missing translations?): %s ... — translate them or rerun with --prune"
                 % (len(stale), ", ".join(stale[:5])))
    dates = update_dates(pages, avail, tms)
    write_sitemaps(pages, avail, clusters, dates)
    write_robots()
    write_llms(avail)
    print("built %d pages; languages live: %s" % (len(written), ", ".join("%s(%d)" % (c, len(avail[c])) for c in shipped)))


def update_dates(pages, avail, tms):
    p = os.path.join(I18N, "dates.json")
    dates = json.loads(read(p)) if os.path.exists(p) else {}
    today = datetime.date.today().isoformat()
    new = {}
    for c in CODES[1:]:
        for path in sorted(avail[c]):
            h = sid(json.dumps([(i, tms[c][i]) for i in pages[path]], ensure_ascii=False))
            key = lang_path(c, path)
            old = dates.get(key)
            new[key] = old if old and old[0] == h else [h, today]
    write(p, json.dumps(new, ensure_ascii=False, indent=0, sort_keys=True) + "\n")
    return new


def en_urls():
    """[(path, lastmod, priority)] for every URL in the English sitemap (kept as authored)."""
    src = os.path.join(ROOT, "sitemap-en.xml")
    if not os.path.exists(src):
        src = os.path.join(ROOT, "sitemap.xml")
    x = read(src)
    out = []
    for u in re.findall(r"<url>(.*?)</url>", x, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", u).group(1).strip()
        lm = re.search(r"<lastmod>(.*?)</lastmod>", u)
        pr = re.search(r"<priority>(.*?)</priority>", u)
        cf = re.search(r"<changefreq>(.*?)</changefreq>", u)
        out.append((loc[len(SITE):] if loc.startswith(SITE) else loc, lm.group(1) if lm else None,
                    pr.group(1) if pr else None, cf.group(1) if cf else None))
    return out


def write_sitemaps(pages, avail, clusters, dates):
    urls = en_urls()
    if not urls:
        sys.exit("no URLs found in sitemap.xml / sitemap-en.xml")
    head = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n')
    files = []
    for c in CODES:
        if not avail[c]:
            continue
        rows = []
        for path, lm, pr, cf in urls:
            if path not in avail[c] and not (c == "en"):
                continue
            cl = clusters.get(path, ["en"])
            alts = ""
            if len(cl) > 1:
                alts = "".join('<xhtml:link rel="alternate" hreflang="%s" href="%s%s"/>' % (L[x]["tag"], SITE, lang_path(x, path)) for x in cl)
                alts += '<xhtml:link rel="alternate" hreflang="x-default" href="%s%s"/>' % (SITE, path)
            if c != "en":
                lm = dates.get(lang_path(c, path), [None, lm])[1]
            rows.append("<url><loc>%s%s</loc>%s%s%s%s</url>" % (
                SITE, lang_path(c, path), alts, "<lastmod>%s</lastmod>" % lm if lm else "",
                "<changefreq>%s</changefreq>" % cf if cf else "", "<priority>%s</priority>" % pr if pr else ""))
        name = "sitemap-%s.xml" % c
        write(os.path.join(ROOT, name), head + "\n".join(rows) + "\n</urlset>\n")
        files.append((name, max([r for r in re.findall(r"<lastmod>(.*?)</lastmod>", "\n".join(rows))] or [""])))
    for f in glob.glob(os.path.join(ROOT, "sitemap-*.xml")):
        if os.path.basename(f) not in [x[0] for x in files]:
            os.remove(f)
    idx = '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(
        "<sitemap><loc>%s/%s</loc>%s</sitemap>" % (SITE, f, "<lastmod>%s</lastmod>" % lm if lm else "") for f, lm in files) + "\n</sitemapindex>\n"
    write(os.path.join(ROOT, "sitemap.xml"), idx)


def write_robots():
    p = os.path.join(ROOT, "robots.txt")
    t = read(p) if os.path.exists(p) else "User-agent: *\nAllow: /\n"
    t = re.sub(r"\n*# Sitemap index:[^\n]*\n", "\n", t)
    t = re.sub(r"(?m)^Sitemap:.*\n?", "", t).rstrip("\n")
    t += "\n\n# Sitemap index: lists sitemap-en.xml and one sitemap per language (sitemap-<code>.xml)\nSitemap: %s/sitemap.xml\n" % SITE
    write(p, t)


def write_llms(avail):
    p = os.path.join(ROOT, "llms.txt")
    if not os.path.exists(p):
        return
    orig = t = read(p)
    if "## Other languages" in t:
        t = re.sub(r"## Other languages\n.*?(?=\n## |\Z)", "", t, flags=re.S).rstrip("\n") + "\n"
        t = re.sub(r"\n{3,}", "\n\n", t)
    live = [c for c in CODES[1:] if avail[c]]
    if live:
        lines = ["## Other languages", ""]
        for c in live:
            n = len([x for x in avail[c] if x.startswith("/blog/") and x != "/blog/"])
            lines.append("- [%s](%s%s)%s" % (L[c]["name"], SITE, lang_path(c, "/"),
                         (" · [blog](%s%s) (%d articles translated)" % (SITE, lang_path(c, "/blog/"), n)) if "/blog/" in avail[c] else ""))
        block = "\n".join(lines) + "\n"
        if "\n## FAQ" in t:
            t = t.replace("\n## FAQ", "\n" + block + "\n## FAQ", 1)
        else:
            t = t.rstrip("\n") + "\n\n" + block
    if t != orig:
        write(p, t)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(0)
    if a[0] == "extract":
        cmd_extract()
    elif a[0] == "todo":
        cmd_todo(a[1], a[2:])
    elif a[0] == "merge":
        cmd_merge(a[1], a[2])
    elif a[0] == "status":
        cmd_status()
    elif a[0] == "build":
        cmd_build()
    else:
        print(__doc__)

"""Translate finished HTML pages with a catalogue of English sentences.

The English site is the source of truth. After a page is built in English, every sentence in it is looked up in
src/i18n/<lang>.json and replaced by its translation. Inline markup (links, bold text) is kept by numbering it:
"Read <1>how we pick</1>." has the translation "<1>हम कैसे चुनते हैं</1> पढ़ें।". Sentences that are missing from the
catalogue stay in English and are reported, so a half-translated page can be caught before it goes live.

Product text written by the owner can be left untouched by adding translate="no" to its element.
Standard library only.
"""
import html as htmllib
import json
import re
from pathlib import Path

INLINE = {"a", "abbr", "b", "bdi", "bdo", "cite", "data", "dfn", "em", "i", "kbd", "mark", "q", "s", "samp", "small",
          "span", "strong", "sub", "sup", "time", "u", "var", "wbr", "br", "img", "svg"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
RAW_TEXT = {"script", "style"}
SKIP = {"script", "style", "svg", "pre", "code", "textarea", "head"}
ATTRS = ("aria-label", "title", "alt", "placeholder", "data-label")
META_KEYS = {"description", "og:title", "og:description", "twitter:title", "twitter:description"}

TOKEN = re.compile(r'<!--.*?-->|<!DOCTYPE[^>]*>|<(/?)([A-Za-z][A-Za-z0-9:-]*)((?:[^>"\']|"[^"]*"|\'[^\']*\')*?)(/?)>', re.S | re.I)
PLACEHOLDER = re.compile(r"<(/?)(\d+)(/?)>")
LETTER = re.compile(r"[^\W\d_]", re.U)
ATTR_RE = re.compile(r'(\s)([A-Za-z_:][A-Za-z0-9_:.-]*)(?:="([^"]*)")?')


class Node:
    __slots__ = ("kind", "tag", "raw", "start", "end", "children", "parent", "open_end", "close_start", "attrs")

    def __init__(self, kind, tag=None, raw="", start=0, end=0):
        self.kind, self.tag, self.raw, self.start, self.end = kind, tag, raw, start, end
        self.children, self.parent, self.open_end, self.close_start, self.attrs = [], None, end, end, None


def parse_attrs(raw_open):
    return {m.group(2).lower(): m.group(3) for m in ATTR_RE.finditer(raw_open[raw_open.index(" "):] if " " in raw_open else "")}


def parse(src):
    root = Node("root", "#root", start=0, end=len(src))
    stack = [root]
    pos = 0

    def add_text(a, b):
        if b > a:
            n = Node("text", start=a, end=b, raw=src[a:b])
            n.parent = stack[-1]
            stack[-1].children.append(n)

    for m in TOKEN.finditer(src):
        if m.start() < pos:
            continue
        add_text(pos, m.start())
        pos = m.end()
        text = m.group(0)
        if text.startswith("<!--") or text.upper().startswith("<!DOCTYPE"):
            n = Node("comment", start=m.start(), end=m.end(), raw=text)
            n.parent = stack[-1]
            stack[-1].children.append(n)
            continue
        closing, tag, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if closing:
            for i in range(len(stack) - 1, 0, -1):
                if stack[i].tag == tag:
                    node = stack[i]
                    node.close_start, node.end = m.start(), m.end()
                    del stack[i:]
                    break
            continue
        node = Node("el", tag, raw=text, start=m.start(), end=m.end())
        node.open_end = m.end()
        node.attrs = attrs
        node.parent = stack[-1]
        stack[-1].children.append(node)
        if tag in VOID or selfclose:
            continue
        if tag in RAW_TEXT:
            close = re.compile(r"</%s\s*>" % tag, re.I).search(src, m.end())
            if close:
                node.close_start, node.end = close.start(), close.end()
                pos = close.end()
            continue
        stack.append(node)
    add_text(pos, len(src))
    return root


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def attr_value(node, name):
    m = re.search(r'\s%s="([^"]*)"' % re.escape(name), node.raw)
    return m.group(1) if m else None


class Catalogue:
    def __init__(self, path=None, lang=None):
        self.lang = lang
        self.units = {}
        self.meta = {}
        if path and Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.units = data.get("units", {})
            self.meta = data.get("_meta", {})

    def get(self, key):
        return self.units.get(key)


class Translator:
    """Walks one built page and replaces sentences. With catalogue=None it only collects them."""

    def __init__(self, catalogue=None):
        self.cat = catalogue
        self.found = {}      # key -> kind
        self.missing = {}    # key -> kind
        self.invalid = []    # (key, reason)

    # ---------- keys and placeholders ----------

    def _lookup(self, key, kind):
        self.found.setdefault(key, kind)
        if self.cat is None:
            return None
        value = self.cat.get(key)
        if value is None or not value.strip():
            self.missing.setdefault(key, kind)
            return None
        return value

    def _attr_translate(self, raw_open):
        """Translate the visible attributes (aria-label, title, alt, placeholder, data-label) inside one opening tag."""
        def sub(m):
            name, value = m.group(2).lower(), m.group(3)
            if name not in ATTRS or value is None or not LETTER.search(value):
                return m.group(0)
            key = norm(htmllib.unescape(value))
            tr = self._lookup(key, "attr")
            if tr is None:
                return m.group(0)
            return f'{m.group(1)}{m.group(2)}="{htmllib.escape(tr, quote=True)}"'
        if " " not in raw_open:
            return raw_open
        head, tail = raw_open[:raw_open.index(" ")], raw_open[raw_open.index(" "):]
        return head + ATTR_RE.sub(sub, tail)

    def _meta_translate(self, node):
        if node.tag != "meta":
            return node.raw
        attrs = parse_attrs(node.raw)
        which = (attrs.get("name") or attrs.get("property") or "").lower()
        if which not in META_KEYS or attrs.get("content") is None:
            return node.raw
        key = norm(htmllib.unescape(attrs["content"]))
        tr = self._lookup(key, "meta")
        if tr is None:
            return node.raw
        return re.sub(r'content="[^"]*"', lambda _: 'content="%s"' % htmllib.escape(tr, quote=True), node.raw, count=1)

    # ---------- runs of text and inline markup ----------

    def _build_key(self, src, nodes):
        """Return (key, store) for a run of sibling nodes; store maps placeholder numbers to the original markup."""
        parts, store, counter = [], {}, [0]

        def walk(ns):
            for n in ns:
                if n.kind == "text":
                    parts.append(norm_keep(htmllib.unescape(n.raw)))
                elif n.kind == "comment":
                    continue
                elif n.tag in VOID or n.tag in {"svg"} or n.close_start == n.open_end and n.end == n.open_end or has_no_translate(n):
                    counter[0] += 1
                    store[counter[0]] = (src[n.start:n.end], None)
                    parts.append(f"<{counter[0]}/>")
                else:
                    counter[0] += 1
                    i = counter[0]
                    store[i] = (self._attr_translate(n.raw), src[n.close_start:n.end])
                    parts.append(f"<{i}>")
                    walk(n.children)
                    parts.append(f"</{i}>")
        walk(nodes)
        return norm("".join(parts)), store

    def _rebuild(self, translation, store):
        out, pos = [], 0
        for m in PLACEHOLDER.finditer(translation):
            out.append(htmllib.escape(translation[pos:m.start()], quote=False))
            closing, num, selfclose = m.group(1), int(m.group(2)), m.group(3)
            open_raw, close_raw = store[num]
            out.append(close_raw if closing else open_raw)
            pos = m.end()
        out.append(htmllib.escape(translation[pos:], quote=False))
        return "".join(out)

    def _valid(self, key, translation):
        def shape(t):
            return sorted((m.group(1), m.group(2), m.group(3)) for m in PLACEHOLDER.finditer(t))
        if shape(key) != shape(translation):
            return "markers <1> </1> do not match the English"
        depth = []
        for m in PLACEHOLDER.finditer(translation):
            if m.group(3):
                continue
            if m.group(1):
                if not depth or depth.pop() != m.group(2):
                    return "markers are nested in the wrong order"
            else:
                depth.append(m.group(2))
        if depth:
            return "a marker is not closed"
        return None

    def _flush(self, src, run, edits):
        # trim blank text at both ends
        while run and run[0].kind == "text" and not run[0].raw.strip():
            run = run[1:]
        while run and run[-1].kind == "text" and not run[-1].raw.strip():
            run = run[:-1]
        run = [n for n in run if n.kind != "comment"] if len(run) == 1 else run
        if not run:
            return
        text_probe = "".join(htmllib.unescape(n.raw) for n in run if n.kind == "text")
        inner_probe = text_probe + "".join(_descendant_text(n) for n in run if n.kind == "el")
        if not LETTER.search(inner_probe):
            return
        # elements side by side with no words between them (a card's tag, title and summary; a breadcrumb) are separate sentences
        elements = [n for n in run if n.kind == "el"]
        direct = "".join(htmllib.unescape(n.raw) for n in run if n.kind == "text")
        if len(elements) >= 2 and not LETTER.search(direct):
            for n in run:
                if n.kind == "el":
                    self._flush(src, [n], edits)
            return
        # one wrapping inline element (a link, a span): translate what is inside it
        if len(run) == 1 and run[0].kind == "el" and run[0].tag not in VOID and run[0].tag != "svg" and not has_no_translate(run[0]):
            el = run[0]
            raw2 = self._attr_translate(el.raw)
            if raw2 != el.raw:
                edits.append((el.start, el.open_end, raw2))
            self._container(src, el, edits, attrs_done=True)
            return
        key, store = self._build_key(src, run)
        if not LETTER.search(re.sub(r"</?\d+/?>", "", key)):
            return
        tr = self._lookup(key, "text")
        if tr is None:
            return
        bad = self._valid(key, tr)
        if bad:
            self.invalid.append((key, bad))
            return
        start = run[0].start
        end = run[-1].end
        edits.append((start, end, self._rebuild(tr, store)))

    def _container(self, src, node, edits, attrs_done=False):
        if node.tag in SKIP or has_no_translate(node):
            return
        if node.kind == "el" and not attrs_done:
            raw2 = self._meta_translate(node) if node.tag == "meta" else self._attr_translate(node.raw)
            if raw2 != node.raw:
                edits.append((node.start, node.open_end, raw2))
        run = []
        for child in node.children:
            if child.kind == "text" or (child.kind == "el" and child.tag in INLINE):
                run.append(child)
            elif child.kind == "comment":
                continue
            else:
                self._flush(src, run, edits)
                run = []
                if child.tag in VOID:
                    if child.kind == "el":
                        raw2 = self._meta_translate(child) if child.tag == "meta" else self._attr_translate(child.raw)
                        if raw2 != child.raw:
                            edits.append((child.start, child.end, raw2))
                else:
                    self._container(src, child, edits)
        self._flush(src, run, edits)

    def translate(self, src):
        root = parse(src)
        edits = []
        # <head> holds the title and meta text; handle it before skipping it for body text
        for head in _find(root, "head"):
            for child in head.children:
                if child.kind != "el":
                    continue
                if child.tag == "title":
                    self._container(src, child, edits)
                elif child.tag == "meta":
                    raw2 = self._meta_translate(child)
                    if raw2 != child.raw:
                        edits.append((child.start, child.end, raw2))
        self._container(src, root, edits)
        for body in _find(root, "body"):
            pass
        # apply from the back so offsets stay valid
        edits = sorted(set(edits), key=lambda e: e[0], reverse=True)
        out, last = src, len(src) + 1
        for start, end, repl in edits:
            if end > last:
                continue  # nested edit, outer one wins
            out = out[:start] + repl + out[end:]
            last = start
        return out


def norm_keep(text):
    # keep a single leading/trailing space as one space so words around markers stay separated
    lead = " " if text[:1].isspace() else ""
    trail = " " if text[-1:].isspace() else ""
    core = re.sub(r"\s+", " ", text.strip())
    return (lead + core + trail) if core else (" " if text else "")


def has_no_translate(node):
    return node.kind == "el" and 'translate="no"' in node.raw


def _descendant_text(node):
    if node.kind == "text":
        return htmllib.unescape(node.raw)
    if node.kind == "el" and node.tag in ("svg", "script", "style"):
        return ""
    return "".join(_descendant_text(c) for c in node.children)


def _find(node, tag):
    for c in node.children:
        if c.kind == "el":
            if c.tag == tag:
                yield c
            else:
                yield from _find(c, tag)


# ---------- links ----------

LINK = re.compile(r'(\s(?:href|action)=")(/[^"]*)(")')
TAG = re.compile(r"<[A-Za-z][^>]*>")


def localize_links(page, prefix, known):
    """Point root-relative links at the same language, for pages that exist in that language.
    Language switcher links (they carry hreflang) already hold their exact target and are left alone."""
    def sub_link(m):
        url = m.group(2)
        path = re.split(r"[?#]", url, 1)[0]
        if path in known:
            return m.group(1) + prefix + url + m.group(3)
        return m.group(0)

    def sub_tag(m):
        tag = m.group(0)
        if "hreflang=" in tag:
            return tag
        return LINK.sub(sub_link, tag)
    return TAG.sub(sub_tag, page)

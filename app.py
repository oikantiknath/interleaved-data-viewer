#!/usr/bin/env python3
import os, json, pathlib, base64
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from typing import List, Dict

# ---------- Paths ----------
APP_DIR = pathlib.Path(__file__).parent.resolve()
# Your repo has domain folders at the root (culture/, demography/, ...):
DEFAULT_BASE = APP_DIR  # <— IMPORTANT: repo root
BASE_STR = st.secrets.get("DATA_BASE", os.environ.get("DATA_BASE", str(DEFAULT_BASE)))
BASE = pathlib.Path(BASE_STR).resolve()

ORIG_PREFIX = pathlib.Path("/data/oikantik_sarvam_ai/wiki-data")
LOCAL_BASE = BASE

st.set_page_config(page_title="Wiki Samples Viewer", layout="wide")

# ---------- Helpers ----------
def fix_image_path(path: str) -> pathlib.Path:
    try:
        p = pathlib.Path(path)
        if str(p).startswith(str(ORIG_PREFIX)):
            rel = p.relative_to(ORIG_PREFIX)
            return LOCAL_BASE / rel
        return p
    except Exception:
        return pathlib.Path(path)

@st.cache_data
def list_domains(base: pathlib.Path) -> List[str]:
    if not base.exists():
        return []
    # domains are top-level folders that contain at least a markdown/ subfolder
    out = []
    for p in sorted([q for q in base.iterdir() if q.is_dir()]):
        if (p / "markdown").exists() or (p / "text").exists() or (p / "html").exists():
            out.append(p.name)
    return out

@st.cache_data
def list_langs(base: pathlib.Path, domain: str) -> List[str]:
    d = base / domain
    langs = set()
    for sub in ("markdown", "html", "text"):
        p = d / sub
        if p.exists():
            for c in p.iterdir():
                if c.is_dir():
                    langs.add(c.name)
    return sorted(langs)

@st.cache_data
def list_articles(base: pathlib.Path, domain: str, lang: str) -> List[str]:
    d = base / domain
    html_stems = {p.stem for p in (d / "html" / lang).glob("*.html")} | {
        p.stem for p in (d / "html" / lang).glob("*.htm")
    }
    md_stems = {p.stem for p in (d / "markdown" / lang).glob("*.md")}
    return sorted(html_stems & md_stems) if html_stems else sorted(md_stems)

@st.cache_data
def load_paths(base: pathlib.Path, domain: str, lang: str, stem: str) -> Dict[str, pathlib.Path]:
    d = base / domain
    html = d / "html" / lang / f"{stem}.html"
    if not html.exists():
        html = d / "html" / lang / f"{stem}.htm"
    md = d / "markdown" / lang / f"{stem}.md"
    js = d / "text" / lang / f"{stem}.json"
    return {"html": html, "md": md, "json": js}

@st.cache_data
def load_json_record(path: pathlib.Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

@st.cache_data
def canonical_url_from_html(html_path: pathlib.Path) -> str | None:
    if not html_path.exists():
        return None
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    try:
        soup = BeautifulSoup(raw, "lxml")
    except Exception:
        soup = BeautifulSoup(raw, "html.parser")
    can = soup.find("link", rel="canonical")
    return can.get("href") if can and can.get("href") else None

@st.cache_data
def img_to_data_uri(p: pathlib.Path) -> str | None:
    if not p.exists():
        return None
    suffix = p.suffix.lower()
    mime = (
        "image/jpeg" if suffix in (".jpg", ".jpeg")
        else "image/png" if suffix == ".png"
        else "image/gif" if suffix == ".gif"
        else "application/octet-stream"
    )
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"

def render_blocks_as_html(rec) -> str:
    css = """
    <style>
      body { font-family: system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; line-height:1.55; }
      .pane { height: 900px; overflow:auto; padding-right: 8px; }
      h1,h2,h3,h4 { margin: 0.6rem 0 0.4rem; }
      p { margin: 0.5rem 0; }
      table { border-collapse: collapse; margin: 0.5rem 0; width:100%; }
      th, td { border: 1px solid #ddd; padding: 6px; vertical-align: top; }
      img { max-width: 100%; height: auto; display: block; margin: 0.25rem 0; }
      em { color: #555; }
    </style>
    """
    html = ['<div class="pane">']
    last_sec = []
    for b in rec.get("blocks", []):
        sec = b.get("section", [])
        if sec != last_sec:
            for i, s in enumerate(sec):
                lvl = min(4, i + 2)
                html.append(f"<h{lvl}>{s}</h{lvl}>")
            last_sec = sec
        typ = b.get("type")
        if typ == "text":
            txt = (b.get("text") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html.append(f"<p>{txt}</p>")
        elif typ == "table":
            lines = [ln.strip() for ln in (b.get("md") or "").strip().splitlines() if ln.strip()]
            start = 0
            if lines and lines[0].startswith("*") and lines[0].endswith("*"):
                cap = lines[0].strip("*")
                html.append(f"<p><em>{cap}</em></p>")
                start = 1
            if len(lines) - start >= 2:
                header = [c.strip() for c in lines[start].strip("| ").split("|")]
                html.append("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in header) + "</tr></thead><tbody>")
                for ln in lines[start + 2:]:
                    cells = [c.strip() for c in ln.strip("| ").split("|")]
                    if len(cells) < len(header): cells += [""] * (len(header) - len(cells))
                    if len(cells) > len(header): cells = cells[:len(header)]
                    html.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
                html.append("</tbody></table>")
        elif typ == "image":
            local = fix_image_path(b.get("local_path", ""))
            uri = img_to_data_uri(local)
            alt = (b.get("alt") or "").replace('"', "&quot;")
            cap = b.get("caption")
            if uri:
                html.append(f'<img src="{uri}" alt="{alt}"/>')
                if cap:
                    cap_esc = cap.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    html.append(f"<p><em>{cap_esc}</em></p>")
            else:
                html.append(f'<p><em>Missing image: {local}</em></p>')
    html.append("</div>")
    return css + "\n".join(html)

# ---------- UI ----------
st.title("🗂️ Wiki Samples Viewer")

# Debug panel (helps confirm what Cloud sees)
with st.sidebar:
    st.caption("Data root (BASE)")
    st.code(str(BASE))
    if BASE.exists():
        # show first few subdirs
        subdirs = [p.name for p in BASE.iterdir() if p.is_dir()]
        st.caption("Top-level folders found:")
        st.write(subdirs[:15])

domains = list_domains(BASE)
if not domains:
    st.error(
        f"No domain folders found at:\n`{BASE}`\n\n"
        "Your repo layout should have top-level folders like `culture/`, `demography/`, etc.\n"
        "If your data is elsewhere, set `DATA_BASE` in Secrets to that path."
    )
    st.stop()

c0, c1, c2 = st.columns([1, 1, 2], gap="small")
with c0:
    domain = st.selectbox("Domain", options=domains, index=0)
langs = list_langs(BASE, domain)
if not langs:
    st.warning("No language folders in selected domain."); st.stop()
with c1:
    lang = st.selectbox("Language", options=langs, index=0)
articles = list_articles(BASE, domain, lang)
if not articles:
    st.warning("No articles found for this domain/lang."); st.stop()
with c2:
    stem = st.selectbox("Article", options=articles, index=0)

paths = load_paths(BASE, domain, lang, stem)

left, right = st.columns(2, gap="large")

# LEFT: live Wikipedia (scrollable iframe)
with left:
    st.subheader("Wikipedia (live)")
    page_url = None
    rec = load_json_record(paths["json"])
    if rec and rec.get("page_url"):
        page_url = rec["page_url"]
    if not page_url:
        page_url = canonical_url_from_html(paths["html"])
    if page_url:
        try:
            components.iframe(page_url, height=900, scrolling=True)
        except Exception:
            st.link_button("Open on Wikipedia ↗", page_url)
    else:
        st.info("Canonical URL not found.")

# RIGHT: scrollable Markdown (rendered as HTML with base64 images)
with right:
    st.subheader("Markdown (blocks)")
    if not rec:
        rec = load_json_record(paths["json"])
    if rec:
        html_panel = render_blocks_as_html(rec)
        components.html(html_panel, height=900, scrolling=False)
    else:
        md_text = paths["md"].read_text(encoding="utf-8", errors="ignore")
        components.html(
            f"""<div style="height:900px; overflow:auto; border:1px solid #ddd; padding:8px; white-space:pre-wrap; font-family:monospace">
            {md_text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}
            </div>""",
            height=900,
            scrolling=False,
        )

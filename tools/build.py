"""Builds the library from data/*.json.

    python3 tools/build.py          validate, then write README.md, prompts/,
                                    prompts.json, llms.txt and the site in docs/
    python3 tools/build.py --check  validate only

Everything it writes is generated; edit data/ or guides/ instead.
"""

import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdlite  # noqa: E402
import schema as S  # noqa: E402
import validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPO = "gunjchhetri/ai-coloring-book-prompts"
REPO_URL = f"https://github.com/{REPO}"
SITE = "https://gunjchhetri.github.io/ai-coloring-book-prompts"
INKCHAMPS = "https://inkchamps.com"
CAMPAIGN = "ai-coloring-book-prompts"
SITE_NAME = "AI Coloring Book Prompts"
TODAY = date.today().isoformat()

CATEGORY_ORDER = list(S.CATEGORIES)
NAV_LABELS = {
    "coloring-books": "Coloring", "story-coloring-books": "Story coloring",
    "illustrated-story-books": "Picture books", "activity-books": "Activity",
    "educational-coloring-books": "Educational", "kdp-book-covers": "KDP covers",
}


def ages_of(page):
    found = {p.get("ageGroup") for p in page["prompts"] if p.get("ageGroup")}
    return [a for a in S.AGE_GROUPS if a in found]
CATEGORY_BLURBS = {
    "coloring-books": "Themed coloring books for kids, teens and adults: animals, mandalas, holidays, ABC and more.",
    "story-coloring-books": "Coloring books that tell one story, a line or two of text on every page.",
    "illustrated-story-books": "Full-colour children's picture books: bedtime, friendship, bravery, birthdays.",
    "activity-books": "Mazes, word search, sudoku, tracing, dot-to-dot and spot the difference, all themed.",
    "educational-coloring-books": "Color-to-learn books that teach one idea per page: life cycles, space, the body.",
    "kdp-book-covers": "Print-ready Amazon KDP paperback covers with front, spine and back.",
}

GUIDES = [
    ("how-to-use-these-prompts", "How to use these prompts"),
    ("gemini-gem-and-custom-gpt", "Make a Gemini Gem or custom GPT that writes book prompts"),
    ("ai-agents-mcp", "Order books from Claude, Cursor and other AI agents (MCP)"),
    ("sell-ai-coloring-books-on-amazon-kdp", "Can you sell AI coloring books on Amazon KDP?"),
]


# ---------------------------------------------------------------- data

def load():
    by_category = {}
    for path in sorted((ROOT / "data").glob("*.json")):
        data = json.loads(path.read_text())
        by_category.setdefault(data["category"], []).extend(data["pages"])
    return {c: by_category[c] for c in CATEGORY_ORDER if c in by_category}


def main_text(category, prompt):
    fields = prompt["fields"]
    if category == "illustrated-story-books":
        return fields.get("storyPrompt") or fields.get("description", "")
    return fields.get("description", "")


def credits(category, prompt):
    rates = S.CATEGORIES[category]["rates"]
    if rates is None:
        return 2, 2  # a cover: one credit for each side drawn
    pages = prompt["numberOfPages"]
    return pages * rates[0], pages * rates[1]


def make_link(category, prompt, slug, index, source):
    params = {
        "tool": S.CATEGORIES[category]["website_tool"],
        "prompt": main_text(category, prompt),
        "utm_source": source,
        "utm_medium": "prompt_library",
        "utm_campaign": CAMPAIGN,
        "utm_content": f"{slug}-{index + 1}",
    }
    return f"{INKCHAMPS}/dashboard/?{urlencode(params, quote_via=quote)}"


def inkchamps_link(source, content):
    params = {"utm_source": source, "utm_medium": "prompt_library", "utm_campaign": CAMPAIGN, "utm_content": content}
    return f"{INKCHAMPS}/?{urlencode(params)}"


def mcp_call(category, prompt):
    args = {}
    if category != "kdp-book-covers":
        args.update(ageGroup=prompt["ageGroup"], numberOfPages=prompt["numberOfPages"], highQuality=prompt["highQuality"])
    if prompt.get("pageSize"):
        args["pageSize"] = prompt["pageSize"]
    args.update(prompt["fields"])
    return {"tool": S.CATEGORIES[category]["tool"], "arguments": args}


def settings(category, prompt):
    """Ordered (label, value) pairs a reader scans before the brief."""
    fields = prompt["fields"]
    rows = []
    if category != "kdp-book-covers":
        rows.append(("Ages", prompt["ageGroup"]))
        rows.append(("Pages", str(prompt["numberOfPages"])))
    rows.append(("Size", f'{prompt.get("pageSize", "8.5x11").replace("x", " × ")} in'))
    if "style" in fields:
        style = fields["style"]
        label = S.ILLUSTRATION_STYLE_LABELS.get(style) or style.replace("_", " ").capitalize()
        rows.append(("Style", label))
    if "complexity" in fields:
        rows.append(("Detail", fields["complexity"].capitalize()))
    if fields.get("pageCategory") in ("concept", "instructional"):
        rows.append(("Layout", "One item per page, with its caption"))
    if "pageTemplate" in fields:
        rows.append(("Layout", S.PAGE_TEMPLATE_LABELS[fields["pageTemplate"]]))
    if "activities" in fields:
        per = fields.get("pagesByType") or {}
        acts = [f'{S.ACTIVITY_LABELS[a]}{f" ({per[a]})" if a in per else ""}' for a in fields["activities"]]
        rows.append(("Activities", ", ".join(acts)))
    if "mazeStyles" in fields:
        rows.append(("Maze styles", ", ".join(m.replace("_", " ") for m in fields["mazeStyles"])))
    if "bookType" in fields:
        rows.append(("Interior", f'{fields["bookType"].replace("_", " ")}, {fields["sheetCount"]} sheets'))
    if category != "kdp-book-covers":
        rows.append(("Quality", "Premium" if prompt["highQuality"] else "Standard"))
    std, premium = credits(category, prompt)
    rows.append(("InkChamps credits", f"{std} Standard · {premium} Premium" if category != "kdp-book-covers" else f"{std}"))
    return rows


def related(pages, slug, n=6):
    others = [p for p in pages if p["slug"] != slug]
    start = next((i for i, p in enumerate(pages) if p["slug"] == slug), 0)
    ordered = others[start:] + others[:start]
    return ordered[:n]


def count_prompts(data):
    return sum(len(p["prompts"]) for pages in data.values() for p in pages)


def github_anchor(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 \-]", "", text)
    return text.replace(" ", "-")


# ---------------------------------------------------------------- markdown (GitHub)

def md_prompt_page(category, page, pages):
    meta = S.CATEGORIES[category]
    out = [f"# {page['title']}", "", page["intro"], ""]
    out += [
        f"> **Make any of these in one click.** Each prompt opens in [InkChamps]({inkchamps_link('github', page['slug'])}), "
        f"the AI book maker that turns a brief into a print-ready PDF for Amazon KDP, Etsy or home printing. "
        f"Or copy the brief into any AI tool you like.",
        "",
        "**Prompts on this page:** " + " · ".join(
            f"[{p['name']}](#{github_anchor(f'{i + 1}. ' + p['name'])})" for i, p in enumerate(page["prompts"])
        ),
        "",
    ]
    for i, prompt in enumerate(page["prompts"]):
        out += [f"## {i + 1}. {prompt['name']}", ""]
        out.append(" · ".join(f"**{k}:** {v}" for k, v in settings(category, prompt)))
        out += ["", "```text", main_text(category, prompt), "```", ""]
        extra = prompt["fields"].get("additionalInstructions")
        if extra:
            out += [f"**Extra direction:** {extra}", ""]
        out += [
            f"[**▶ Make this {meta['singular']} on InkChamps**]({make_link(category, prompt, page['slug'], i, 'github')})",
            "",
            f"*Why it works:* {prompt['why']}",
            "",
            "<details><summary>Exact settings for AI agents (InkChamps MCP)</summary>",
            "",
            "```json",
            json.dumps(mcp_call(category, prompt), indent=2, ensure_ascii=False),
            "```",
            "",
            "</details>",
            "",
        ]
    out += [f"## Tips for {page['title'].split(' Prompts')[0].lower()}", ""]
    out += [f"- {tip}" for tip in page["tips"]]
    out += ["", "## More prompts like these", ""]
    out += [f"- [{p['title']}]({p['slug']}.md)" for p in related(pages, page["slug"])]
    out += [
        "",
        "---",
        "",
        f"[All {meta['label'].lower()} prompts](README.md) · [Every prompt in the library](../../README.md) · "
        f"[Browse on the website]({SITE}/{category}/{page['slug']}/) · "
        f"Prompts licensed [CC BY 4.0](../../LICENSE) by [InkChamps]({inkchamps_link('github', 'footer')})",
        "",
    ]
    return "\n".join(out)


def md_category_index(category, pages):
    meta = S.CATEGORIES[category]
    n = sum(len(p["prompts"]) for p in pages)
    out = [
        f"# {meta['label']} Prompts",
        "",
        f"{n} ready-to-use AI prompts for {meta['label'].lower()}, on {len(pages)} themes. "
        f"{CATEGORY_BLURBS[category]} Every prompt opens in "
        f"[InkChamps]({inkchamps_link('github', category)}) with one click and comes out as a print-ready PDF.",
        "",
        "| Theme | Prompts | Ages |",
        "|---|---|---|",
    ]
    for page in pages:
        out.append(f"| [{page['title']}]({page['slug']}.md) | {len(page['prompts'])} | {', '.join(ages_of(page)) or 'any'} |")
    out += ["", f"[← Every prompt in the library](../../README.md)", ""]
    return "\n".join(out)


def guide_markdown(name):
    return (ROOT / "guides" / f"{name}.md").read_text()


def md_readme(data):
    total = count_prompts(data)
    themes = sum(len(p) for p in data.values())
    out = [
        "# AI Coloring Book Prompts",
        "",
        f"**{total} tested AI prompts for coloring books, story books, activity books and KDP covers** — "
        f"{themes} themes, from dinosaurs and mandalas to ABC books, mazes and bedtime stories. "
        "Each one is a ready-made brief: copy it into any AI tool, or open it in "
        f"[InkChamps]({inkchamps_link('github', 'readme-intro')}) with one click and download a print-ready PDF "
        "for Amazon KDP, Etsy or home printing.",
        "",
        f"[**Browse the prompts on the website →**]({SITE}/)  ·  [**Make a book on InkChamps →**]({inkchamps_link('github', 'readme-top')})",
        "",
        "## What is in the library",
        "",
        "| Kind of book | Themes | Prompts |",
        "|---|---|---|",
    ]
    for category, pages in data.items():
        meta = S.CATEGORIES[category]
        out.append(f"| [{meta['label']}](prompts/{category}/README.md) — {CATEGORY_BLURBS[category]} | {len(pages)} | {sum(len(p['prompts']) for p in pages)} |")
    out += ["", "## Every theme", ""]
    for category, pages in data.items():
        meta = S.CATEGORIES[category]
        out.append(f"**{meta['label']}:** " + " · ".join(
            f"[{p['title'].split(' Prompts')[0].replace(' Coloring Book', '').replace(' Story Book', '').replace(' Activity Book', '')}](prompts/{category}/{p['slug']}.md)"
            for p in pages
        ))
        out.append("")
    out += [
        "## How to use a prompt",
        "",
        "1. **Pick a theme** and a prompt that fits your reader's age.",
        f"2. **Click \"Make this book on InkChamps\".** The brief opens in the [InkChamps]({inkchamps_link('github', 'readme-howto')}) creator, already filled in. Check the age and page count, press create, and download the PDF.",
        "3. **Or copy the brief** into ChatGPT, Gemini, Claude or another image tool. The briefs describe the pages, not one tool's settings, so they travel.",
        "4. **Using an AI agent?** Every prompt has its exact InkChamps MCP call under *Exact settings for AI agents*. See the [agent guide](guides/ai-agents-mcp.md).",
        "",
        "Every prompt states its age band, page count, page size and style, because a book for a 4-year-old and a book for an adult are drawn differently: line weight, detail and how much background a page carries all change with age.",
        "",
        "## Guides",
        "",
    ]
    out += [f"- [{title}](guides/{name}.md)" for name, title in GUIDES]
    out += [
        "",
        "## FAQ",
        "",
    ]
    for q, a in FAQ:
        out += [f"**{q}**", "", a, ""]
    out += [
        "## Contribute",
        "",
        "New themes and better briefs are welcome. Add a prompt to the right file in [`data/`](data/README.md), run `python3 tools/build.py`, and open a pull request. "
        "The build checks every prompt against what InkChamps accepts, so a prompt that passes works first time.",
        "",
        "## License",
        "",
        f"The prompts are licensed [CC BY 4.0](LICENSE): use them, sell the books you make with them, and adapt them. "
        f"If you republish the prompts themselves, credit \"AI Coloring Book Prompts by InkChamps\" with a link to this repository. "
        f"The build scripts are MIT.",
        "",
        f"Made by [InkChamps]({inkchamps_link('github', 'readme-footer')}) — the AI book maker for KDP sellers, Etsy shops, parents and teachers.",
        "",
    ]
    return "\n".join(out)


FAQ = [
    ("What is the best prompt for an AI coloring book?",
     "One that names the reader's age, the number of pages and concrete subjects for those pages — \"a stegosaurus watering a vegetable garden\" rather than \"cute dinosaurs\". "
     "Describe what is on the pages and leave drawing rules (line weight, no shading) to the tool. Every prompt here follows that pattern."),
    ("Can I sell coloring books made from these prompts on Amazon KDP or Etsy?",
     "Yes. The prompts are CC BY 4.0 and use only original characters, no brands or famous characters. Amazon KDP asks you to disclose AI-generated images when you publish; "
     "see [KDP's content guidelines](https://kdp.amazon.com/en_US/help/topic/G200672390) and our [KDP guide](guides/sell-ai-coloring-books-on-amazon-kdp.md)."),
    ("How many pages should a coloring book have?",
     "Amazon KDP paperbacks need at least 24 pages. Most kids' coloring books sell at 30 to 50 single-sided pages; toddler books can be shorter, and a list book "
     "(A to Z, numbers 1 to 20) has exactly one page per item."),
    ("What size is best for a KDP coloring book?",
     "8.5 × 11 in is the standard for coloring and activity books. 8.5 × 8.5 in suits picture books and toddler books, and 6 × 9 in suits journals and small gift books."),
    ("Do these prompts work in ChatGPT, Gemini or Midjourney?",
     "The briefs are plain English, so they work as a starting point anywhere. One click on InkChamps turns a brief into a whole consistent book (every page, the right line weight for the age, a print-ready PDF) rather than one image at a time."),
    ("Are the prompts free?",
     "Yes, every prompt is free to use. Making the book on InkChamps uses credits; each prompt lists its cost at Standard and Premium quality."),
]


# ---------------------------------------------------------------- html (GitHub Pages)

CSS = """
:root{--ink:#1f1b18;--muted:#6b625b;--line:#eadfd3;--paper:#fffaf3;--panel:#ffffff;--coral:#f08b53;--sun:#f5b942;--soft:#fff3e2;--accent:#c4602d}
@media (prefers-color-scheme:dark){:root{--ink:#f3ede6;--muted:#b9aea4;--line:#3a332d;--paper:#171412;--panel:#211d1a;--soft:#2a231d;--accent:#f5a06f}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent)}header.site{border-bottom:1px solid var(--line);background:var(--panel)}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}.bar{display:flex;align-items:center;gap:10px 22px;padding-top:12px;padding-bottom:12px;flex-wrap:wrap}.bar .cta{margin-left:auto;padding:8px 16px;font-size:14px}
.brand{font-weight:800;text-decoration:none;color:var(--ink);font-size:18px}.nav{display:flex;gap:16px;flex-wrap:wrap;font-size:14px}.nav a{color:var(--muted);text-decoration:none}
.cta{display:inline-block;background:linear-gradient(135deg,var(--coral),var(--sun));color:#fff!important;text-decoration:none;font-weight:700;padding:10px 18px;border-radius:999px}
main{padding:28px 0 60px}h1{font-size:34px;line-height:1.2;margin:8px 0 12px}h2{font-size:24px;margin:40px 0 10px}h3{font-size:19px}
.lead{font-size:18px;color:var(--muted);max-width:760px}.crumbs{font-size:13px;color:var(--muted)}.crumbs a{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px}.card h3{margin:0 0 6px;font-size:17px}.card p{margin:0;color:var(--muted);font-size:14px}
.card a.stretch{text-decoration:none;color:inherit}
.prompt{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin:22px 0}
.prompt h2{margin:0 0 10px;font-size:21px}.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px;padding:0;list-style:none}
.chips li{background:var(--soft);border-radius:999px;padding:3px 10px;font-size:13px}.chips b{font-weight:600}
.brief{position:relative}.brief pre{white-space:pre-wrap;background:var(--soft);border-radius:12px;padding:16px 18px 16px 18px;margin:0;font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}.brief{padding-top:30px}
.copy{position:absolute;top:0;right:0;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:4px 10px;font-size:12px;cursor:pointer}
.actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:14px 0 6px}.why{color:var(--muted);font-size:15px;margin:8px 0 0}
details{margin-top:10px;font-size:14px}summary{cursor:pointer;color:var(--muted)}details pre{overflow:auto;background:var(--soft);border-radius:10px;padding:12px;font-size:13px}
.tips li{margin:6px 0}.note{background:var(--soft);border-radius:14px;padding:14px 18px;margin:18px 0}
.table{overflow-x:auto}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;font-size:15px}
pre{overflow:auto}code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em}
footer.site{border-top:1px solid var(--line);padding:26px 0 40px;color:var(--muted);font-size:14px}
@media (max-width:700px){h1{font-size:27px}.prompt{padding:16px}.nav{order:3;width:100%;flex-wrap:nowrap;overflow-x:auto;white-space:nowrap;padding-bottom:4px}}
"""

COPY_JS = """document.querySelectorAll('.copy').forEach(function(b){b.addEventListener('click',function(){var t=b.parentNode.querySelector('pre').innerText;navigator.clipboard.writeText(t).then(function(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy'},1500)})})});"""


def esc(text):
    return html.escape(text, quote=True)


def page_html(path, title, description, body, breadcrumbs, jsonld=None, depth=0):
    url = f"{SITE}/{path}" if path else f"{SITE}/"
    up = "../" * depth
    crumbs_ld = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": f"{SITE}/{href}" if href else f"{SITE}/"}
            for i, (name, href) in enumerate(breadcrumbs)
        ],
    }
    blocks = [crumbs_ld] + (jsonld or [])
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>' for b in blocks)
    crumbs = " › ".join(
        f'<a href="{up}{href}">{esc(name)}</a>' if i < len(breadcrumbs) - 1 else esc(name)
        for i, (name, href) in enumerate(breadcrumbs)
    ) if len(breadcrumbs) > 1 else ""
    nav = "".join(f'<a href="{up}{c}/">{esc(NAV_LABELS[c])}</a>' for c in CATEGORY_ORDER)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary">
<meta name="robots" content="index,follow">
<style>{CSS}</style>
{ld}
</head>
<body>
<header class="site"><div class="wrap bar"><a class="brand" href="{up or './'}">{SITE_NAME}</a><nav class="nav">{nav}</nav><a class="cta" href="{inkchamps_link('github_pages', 'header')}">Make a book</a></div></header>
<main class="wrap">
<div class="crumbs">{crumbs}</div>
{body}
</main>
<footer class="site"><div class="wrap">Free prompts, licensed <a href="{REPO_URL}/blob/main/LICENSE">CC BY 4.0</a>. Source on <a href="{REPO_URL}">GitHub</a> · Made by <a href="{inkchamps_link('github_pages', 'footer')}">InkChamps</a>, the AI book maker for KDP sellers, Etsy shops, parents and teachers. Updated {TODAY}.</div></footer>
<script>{COPY_JS}</script>
</body>
</html>
"""


def html_prompt_page(category, page, pages):
    meta = S.CATEGORIES[category]
    parts = [f"<h1>{esc(page['title'])}</h1>", f'<p class="lead">{esc(page["intro"])}</p>',
             f'<div class="note">Each prompt below opens in <a href="{inkchamps_link("github_pages", page["slug"])}">InkChamps</a> with one click, '
             f'already filled in, and comes out as a print-ready PDF. Or press <b>Copy</b> and use the brief in any AI tool.</div>']
    items = []
    for i, prompt in enumerate(page["prompts"]):
        chips = "".join(f"<li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in settings(category, prompt))
        extra = prompt["fields"].get("additionalInstructions")
        link = make_link(category, prompt, page["slug"], i, "github_pages")
        parts.append(f"""<section class="prompt" id="prompt-{i + 1}">
<h2>{i + 1}. {esc(prompt['name'])}</h2>
<ul class="chips">{chips}</ul>
<div class="brief"><pre>{esc(main_text(category, prompt))}</pre><button class="copy" type="button">Copy</button></div>
{f'<p><b>Extra direction:</b> {esc(extra)}</p>' if extra else ''}
<div class="actions"><a class="cta" href="{esc(link)}">▶ Make this {esc(meta['singular'])} on InkChamps</a></div>
<p class="why"><b>Why it works:</b> {esc(prompt['why'])}</p>
<details><summary>Exact settings for AI agents (InkChamps MCP)</summary><pre>{esc(json.dumps(mcp_call(category, prompt), indent=2, ensure_ascii=False))}</pre></details>
</section>""")
        items.append({"@type": "ListItem", "position": i + 1, "name": prompt["name"], "url": f"{SITE}/{category}/{page['slug']}/#prompt-{i + 1}"})
    parts.append(f"<h2>Tips for {esc(page['title'].split(' Prompts')[0].lower())}</h2>")
    parts.append('<ul class="tips">' + "".join(f"<li>{esc(t)}</li>" for t in page["tips"]) + "</ul>")
    parts.append("<h2>More prompts like these</h2>")
    parts.append('<div class="grid">' + "".join(
        f'<div class="card"><h3><a href="../{p["slug"]}/">{esc(p["title"])}</a></h3><p>{esc(p["metaDescription"])}</p></div>'
        for p in related(pages, page["slug"])
    ) + "</div>")
    jsonld = [{
        "@context": "https://schema.org", "@type": "ItemList", "name": page["title"],
        "description": page["metaDescription"], "numberOfItems": len(items), "itemListElement": items,
    }]
    return page_html(
        f"{category}/{page['slug']}/", f"{page['title']} | {SITE_NAME}", page["metaDescription"], "\n".join(parts),
        [(SITE_NAME, ""), (meta["label"], f"{category}/"), (page["title"], f"{category}/{page['slug']}/")],
        jsonld, depth=2,
    )


def html_category(category, pages):
    meta = S.CATEGORIES[category]
    n = sum(len(p["prompts"]) for p in pages)
    description = f"{n} free AI prompts for {meta['label'].lower()} on {len(pages)} themes. {CATEGORY_BLURBS[category]}"
    body = [f"<h1>{esc(meta['label'])} Prompts</h1>",
            f'<p class="lead">{esc(description)} Every prompt opens in <a href="{inkchamps_link("github_pages", category)}">InkChamps</a> with one click and comes out as a print-ready PDF.</p>',
            '<div class="grid">']
    body += [f'<div class="card"><h3><a href="{p["slug"]}/">{esc(p["title"])}</a></h3><p>{esc(p["metaDescription"])}</p></div>' for p in pages]
    body.append("</div>")
    return page_html(f"{category}/", f"{meta['label']} Prompts ({n} free AI prompts) | {SITE_NAME}", description[:158],
                     "\n".join(body), [(SITE_NAME, ""), (meta["label"], f"{category}/")], depth=1)


def html_home(data):
    total = count_prompts(data)
    themes = sum(len(p) for p in data.values())
    description = (f"{total} free AI prompts for coloring books, story books, activity books and KDP covers. "
                   "Copy them or make the book in one click, print-ready for KDP and Etsy.")
    body = [
        f"<h1>{total} AI Coloring Book Prompts — and story, activity &amp; KDP cover prompts</h1>",
        f'<p class="lead">Ready-made briefs on {themes} themes, from dinosaurs and mandalas to ABC books, mazes and bedtime stories. '
        f'Copy one into any AI tool, or open it in <a href="{inkchamps_link("github_pages", "home-lead")}">InkChamps</a> with one click and download a print-ready PDF for Amazon KDP, Etsy or home printing.</p>',
        f'<p><a class="cta" href="{inkchamps_link("github_pages", "home-hero")}">Make a book on InkChamps</a> &nbsp; <a href="{REPO_URL}">Star the library on GitHub</a></p>',
    ]
    for category, pages in data.items():
        meta = S.CATEGORIES[category]
        body.append(f'<h2><a href="{category}/">{esc(meta["label"])}</a></h2><p>{esc(CATEGORY_BLURBS[category])}</p><div class="grid">')
        body += [f'<div class="card"><h3><a href="{category}/{p["slug"]}/">{esc(p["title"])}</a></h3><p>{len(p["prompts"])} prompts{(" · ages " + esc(", ".join(ages_of(p)))) if ages_of(p) else ""}</p></div>' for p in pages]
        body.append("</div>")
    body.append("<h2>Guides</h2><ul>" + "".join(f'<li><a href="guides/{n}/">{esc(t)}</a></li>' for n, t in GUIDES) + "</ul>")
    body.append("<h2>Questions</h2>")
    for q, a in FAQ:
        body.append(f"<h3>{esc(q)}</h3>{mdlite.to_html(a.replace('guides/', SITE + '/guides/').replace('.md)', '/)'))}")
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a)}}
        for q, a in FAQ]}
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": f"{SITE}/",
               "publisher": {"@type": "Organization", "name": "InkChamps", "url": INKCHAMPS}}
    return page_html("", f"{total} Free AI Coloring Book Prompts (KDP-ready) | Story & Activity Book Prompts", description,
                     "\n".join(body), [(SITE_NAME, "")], [site_ld, faq_ld])


def html_guide(name, title):
    text = guide_markdown(name)
    first = re.search(r"^(?!#)(.+)$", text, re.M)
    description = re.sub(r"[*`\[\]]|\(http[^)]+\)", "", first.group(1))[:155] if first else title
    text = re.sub(r"\]\((?!http)([a-z0-9\-]+)\.md\)", r"](../\1/)", text)
    text = text.replace("](../prompts/", "](../../").replace("/README.md)", "/)")
    text = text.replace("](../prompts.json)", "](../../prompts.json)")
    text = re.sub(r"\]\(\.\./\.\./([a-z\-]+)/([a-z0-9\-]+)\.md\)", r"](../../\1/\2/)", text)
    body = mdlite.to_html(text)
    return page_html(f"guides/{name}/", f"{title} | {SITE_NAME}", description, body,
                     [(SITE_NAME, ""), (title, f"guides/{name}/")], depth=2)


# ---------------------------------------------------------------- outputs

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build():
    data = load()

    # GitHub markdown
    shutil.rmtree(ROOT / "prompts", ignore_errors=True)
    for category, pages in data.items():
        write(ROOT / "prompts" / category / "README.md", md_category_index(category, pages))
        for page in pages:
            write(ROOT / "prompts" / category / f"{page['slug']}.md", md_prompt_page(category, page, pages))
    write(ROOT / "README.md", md_readme(data))

    # Machine-readable: every prompt with its exact order
    records = []
    for category, pages in data.items():
        for page in pages:
            for i, prompt in enumerate(page["prompts"]):
                std, premium = credits(category, prompt)
                records.append({
                    "id": f"{page['slug']}-{i + 1}", "category": category, "theme": page["title"],
                    "name": prompt["name"], "brief": main_text(category, prompt), "why": prompt["why"],
                    "credits": {"standard": std, "premium": premium},
                    "inkchamps": {"mcp": mcp_call(category, prompt), "makeUrl": make_link(category, prompt, page["slug"], i, "prompts_json")},
                    "page": f"{SITE}/{category}/{page['slug']}/#prompt-{i + 1}",
                })
    prompts_json = json.dumps({"name": SITE_NAME, "license": "CC-BY-4.0", "source": REPO_URL, "count": len(records), "prompts": records}, indent=1, ensure_ascii=False)
    write(ROOT / "prompts.json", prompts_json + "\n")

    llms = [f"# {SITE_NAME}", "",
            f"> {len(records)} free, tested AI prompts for coloring books, story coloring books, illustrated children's picture books, activity books (mazes, word search, sudoku, tracing), educational coloring books and Amazon KDP covers. "
            f"Each prompt is a brief with age band, page count, page size and style, and opens in InkChamps ({INKCHAMPS}) with one click to make a print-ready PDF.",
            "", f"Full data with exact InkChamps order settings: {SITE}/prompts.json", ""]
    for category, pages in data.items():
        llms.append(f"## {S.CATEGORIES[category]['label']}")
        llms += [f"- [{p['title']}]({SITE}/{category}/{p['slug']}/): {p['metaDescription']}" for p in pages]
        llms.append("")
    llms.append("## Guides")
    llms += [f"- [{t}]({SITE}/guides/{n}/)" for n, t in GUIDES]
    write(ROOT / "llms.txt", "\n".join(llms) + "\n")

    # Static site for GitHub Pages
    docs = ROOT / "docs"
    shutil.rmtree(docs, ignore_errors=True)
    urls = [f"{SITE}/"]
    write(docs / "index.html", html_home(data))
    for category, pages in data.items():
        write(docs / category / "index.html", html_category(category, pages))
        urls.append(f"{SITE}/{category}/")
        for page in pages:
            write(docs / category / page["slug"] / "index.html", html_prompt_page(category, page, pages))
            urls.append(f"{SITE}/{category}/{page['slug']}/")
    for name, title in GUIDES:
        write(docs / "guides" / name / "index.html", html_guide(name, title))
        urls.append(f"{SITE}/guides/{name}/")
    write(docs / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    write(docs / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    write(docs / "llms.txt", "\n".join(llms) + "\n")
    write(docs / "prompts.json", prompts_json + "\n")
    write(docs / ".nojekyll", "")
    write(docs / "404.html", page_html("404.html", f"Page not found | {SITE_NAME}", "This page moved. Browse every AI coloring book prompt.",
                                      f'<h1>Page not found</h1><p><a href="{SITE}/">Browse every prompt</a></p>', [(SITE_NAME, "")]))
    return len(records), len(urls)


if __name__ == "__main__":
    problems = validate.check()
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} problem(s); nothing written.")
        sys.exit(1)
    if "--check" in sys.argv:
        print("All prompts valid.")
        sys.exit(0)
    prompts, pages = build()
    print(f"Built {prompts} prompts, {pages} site pages.")

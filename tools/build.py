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
import images  # noqa: E402
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
    rows.append(("Credits", f"{std} Standard · {premium} Premium" if category != "kdp-book-covers" else f"{std}"))
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
    out = [f"# {page['title']}", ""]
    src = images.image_for(page["slug"], category)
    if src:
        out += [f'<img src="../../{src}" alt="Sample {meta["singular"]} page made with InkChamps" width="320" align="right">', ""]
    out += [page["intro"], ""]
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
        "<p>" + "".join(
            f'<img src="assets/img/{k}.webp" alt="{alt}" width="32%"> '
            for k, alt in (("home-coloring", "A bunny coloring page"), ("home-story", "A picture book page: a boy riding a rocket"), ("home-activity", "A word search activity page"))
        ) + "</p>",
        "",
        "<sub>Sample pages made with InkChamps.</sub>",
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

FONTS = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800"
         "&family=Inter:wght@400;500;600&display=swap")

# Restrained: white pages, InkChamps ink for text and the primary action, and
# InkChamps coral only as a small accent. The colour comes from the book pages.
CSS = """
:root{
  --bg:oklch(99.2% 0.002 285);--surface:#fff;--sunk:oklch(97% 0.006 285);--sunk-2:oklch(94.5% 0.009 285);
  --ink:oklch(26% 0.045 285);--ink-2:oklch(44% 0.03 285);--ink-3:oklch(56% 0.02 285);
  --line:oklch(91.5% 0.01 285);--line-2:oklch(86% 0.014 285);
  --accent:oklch(66% 0.19 32);--accent-ink:oklch(52% 0.17 32);--accent-soft:oklch(96% 0.025 40);
  --radius:14px;--radius-sm:10px;--shadow:0 1px 2px oklch(26% 0.045 285 / .06),0 8px 24px -12px oklch(26% 0.045 285 / .18);
  --display:"Bricolage Grotesque",ui-sans-serif,system-ui,sans-serif;--body:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --ease:cubic-bezier(.22,1,.36,1);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;color-scheme:light}
body{margin:0;background:var(--bg);color:var(--ink);font:400 16px/1.6 var(--body);-webkit-font-smoothing:antialiased}
img{display:block;max-width:100%;height:auto}
a{color:inherit}
:focus-visible{outline:2px solid var(--accent-ink);outline-offset:3px;border-radius:4px}
.wrap{width:min(1160px,100% - 40px);margin-inline:auto}
h1,h2,h3{font-family:var(--display);color:var(--ink);text-wrap:balance;letter-spacing:-0.02em;margin:0}
h1{font-size:clamp(2.1rem,1.4rem + 2.6vw,3.5rem);line-height:1.05;font-weight:800}
h2{font-size:clamp(1.5rem,1.2rem + 1vw,2rem);line-height:1.15;font-weight:700}
h3{font-size:1.125rem;line-height:1.3;font-weight:700}
p{margin:0}
.lead{font-size:clamp(1.05rem,1rem + .3vw,1.2rem);color:var(--ink-2);max-width:62ch;text-wrap:pretty}
.muted{color:var(--ink-2)}

/* header */
.top{position:sticky;top:0;z-index:10;background:oklch(99.2% 0.002 285 / .9);backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;gap:28px;min-height:64px}
.brand{display:flex;align-items:baseline;gap:8px;text-decoration:none;white-space:nowrap}
.brand b{font:800 1.12rem/1 var(--display);letter-spacing:-0.02em}
.brand span{font-size:.8rem;color:var(--ink-3)}
.nav{display:flex;gap:4px;margin-left:auto}
.nav a{white-space:nowrap;text-decoration:none;color:var(--ink-2);font-size:.92rem;font-weight:500;padding:8px 10px;border-radius:8px;transition:background .2s var(--ease),color .2s var(--ease)}
.nav a:hover,.nav a[aria-current]{color:var(--ink);background:var(--sunk)}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font:600 .95rem/1 var(--body);text-decoration:none;border-radius:999px;padding:13px 20px;border:1px solid transparent;cursor:pointer;transition:transform .25s var(--ease),background .2s var(--ease),border-color .2s var(--ease),box-shadow .25s var(--ease)}
.btn-primary{background:var(--ink);color:#fff}
.btn-primary:hover{background:oklch(33% 0.06 285);transform:translateY(-1px);box-shadow:0 10px 20px -10px oklch(26% 0.045 285 / .5)}
.btn-ghost{background:var(--surface);color:var(--ink);border-color:var(--line-2)}
.btn-ghost:hover{border-color:var(--ink-3)}
.btn-sm{padding:9px 14px;font-size:.85rem}
.arrow{transition:transform .25s var(--ease)}
.btn:hover .arrow,.more:hover .arrow{transform:translateX(3px)}

/* home hero */
.hero{padding:clamp(40px,6vw,88px) 0 clamp(40px,5vw,72px);display:grid;grid-template-columns:1.05fr .95fr;gap:clamp(32px,5vw,72px);align-items:center}
.hero h1 .accent{color:oklch(59% 0.2 31)}
.hero .lead{margin-top:20px}
.hero .actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:32px}
.facts{display:flex;flex-wrap:wrap;gap:8px 22px;margin:28px 0 0;padding:0;list-style:none;color:var(--ink-2);font-size:.92rem}
.facts b{color:var(--ink);font-weight:600}
.stack{position:relative;aspect-ratio:1/0.92}
.sheet{position:absolute;background:#fff;border-radius:12px;padding:10px;box-shadow:var(--shadow);border:1px solid var(--line);overflow:hidden;animation:settle .9s var(--ease) both}
.sheet img{width:100%;height:100%;object-fit:cover;border-radius:6px}
.sheet:nth-child(1){left:0;top:8%;width:52%;aspect-ratio:3/4;transform:rotate(-4deg);--r:-4deg}
.sheet:nth-child(2){right:2%;top:0;width:54%;aspect-ratio:1;transform:rotate(3deg);z-index:2;animation-delay:.08s;--r:3deg}
.sheet:nth-child(3){left:24%;bottom:0;width:46%;aspect-ratio:1;transform:rotate(-1deg);z-index:3;animation-delay:.16s;--r:-1deg}
@keyframes settle{from{opacity:.001;transform:translateY(14px) rotate(var(--r))}to{opacity:1;transform:rotate(var(--r))}}

/* sections */
.section{padding:clamp(40px,5vw,72px) 0}
.section + .section{border-top:1px solid var(--line)}
.section-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:24px;flex-wrap:wrap}
.section-head p{margin-top:8px;color:var(--ink-2);max-width:60ch}
.more{display:inline-flex;gap:6px;align-items:center;font-weight:600;font-size:.92rem;text-decoration:none;color:var(--accent-ink);white-space:nowrap}

/* kinds of book */
.kinds{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}
.kind{grid-column:span 3;position:relative;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;text-decoration:none;transition:border-color .25s var(--ease),box-shadow .3s var(--ease),transform .3s var(--ease)}
.kind:nth-child(-n+2){grid-column:span 6}
.kind:hover{border-color:var(--line-2);box-shadow:var(--shadow);transform:translateY(-2px)}
.kind figure{margin:0;aspect-ratio:16/10;background:var(--sunk);overflow:hidden}
.kind:nth-child(-n+2) figure{aspect-ratio:16/9}
.kind figure img{width:100%;height:100%;object-fit:cover;transition:transform .6s var(--ease)}
.kind:hover figure img{transform:scale(1.03)}
.kind .body{padding:16px 18px 18px;display:grid;gap:4px}
.kind .count{font-size:.85rem;color:var(--ink-3);font-weight:500}
.kind p{color:var(--ink-2);font-size:.93rem}

/* theme tiles */
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:20px 16px}
.tile{text-decoration:none;display:grid;gap:10px}
.tile figure{margin:0;aspect-ratio:4/3;border-radius:var(--radius-sm);background:var(--surface);border:1px solid var(--line);overflow:hidden;padding:8px}
.tile figure img{width:100%;height:100%;object-fit:cover;border-radius:6px;transition:transform .6s var(--ease)}
.tile:hover figure img{transform:scale(1.04)}
.tile h3{font-size:1rem;line-height:1.3}
.tile:hover h3{color:var(--accent-ink)}
.tile .meta{font-size:.84rem;color:var(--ink-3);margin-top:-6px}

/* page hero (category, theme) */
.crumbs{font-size:.85rem;color:var(--ink-3);padding-top:24px}
.crumbs a{color:var(--ink-2);text-decoration:none}
.crumbs a:hover{color:var(--ink);text-decoration:underline}
.page-hero{display:grid;grid-template-columns:1.25fr .75fr;gap:clamp(28px,5vw,64px);align-items:center;padding:clamp(20px,3vw,36px) 0 clamp(36px,4vw,56px)}
.page-hero .lead{margin-top:16px}
.page-hero .frame{justify-self:center;width:100%;max-width:380px;background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px;box-shadow:var(--shadow);transform:rotate(1.5deg)}
.page-hero .frame img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px}
.chips{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0;margin:22px 0 0}
.chips li{font-size:.85rem;font-weight:500;color:var(--ink-2);background:var(--sunk);border:1px solid var(--line);padding:5px 11px;border-radius:999px}
.howto{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:center;margin-top:26px;font-size:.92rem;color:var(--ink-2)}

/* prompts */
.prompts{display:grid;gap:20px;padding-bottom:16px}
.prompt{display:grid;grid-template-columns:290px 1fr;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;scroll-margin-top:84px}
.prompt .spec{padding:24px;background:var(--sunk);border-right:1px solid var(--line)}
.prompt .num{font:700 .82rem/1 var(--body);color:var(--accent-ink);font-variant-numeric:tabular-nums}
.prompt h2{font-size:1.3rem;margin-top:8px}
.spec dl{display:grid;gap:9px;margin:20px 0 0;font-size:.88rem}
.spec dl div{display:grid;grid-template-columns:76px 1fr;gap:12px}
.spec dt{color:var(--ink-3)}
.spec dd{margin:0;color:var(--ink);font-weight:500}
.prompt .main{padding:24px;display:grid;gap:16px;align-content:start}
.brief{background:var(--sunk);border-radius:var(--radius-sm)}
.brief-bar{display:flex;align-items:center;justify-content:space-between;padding:10px 10px 0 16px;font-size:.8rem;font-weight:600;color:var(--ink-2)}
.copy{font:600 .8rem/1 var(--body);color:var(--ink);background:#fff;border:1px solid var(--line-2);border-radius:8px;padding:7px 12px;cursor:pointer;transition:border-color .2s var(--ease),background .2s var(--ease)}
.copy:hover{border-color:var(--ink-3)}
.copy[data-done]{background:var(--accent-soft);border-color:var(--accent);color:var(--accent-ink)}
.brief p{padding:10px 16px 16px;font-size:1rem;line-height:1.7;color:var(--ink);white-space:pre-wrap;text-wrap:pretty;max-width:75ch}
.extra{font-size:.92rem;color:var(--ink-2)}
.why{font-size:.93rem;color:var(--ink-2)}
.why b{color:var(--ink);font-weight:600}
.actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
details.agent{font-size:.88rem;border-top:1px solid var(--line);padding-top:12px}
details.agent summary{cursor:pointer;color:var(--ink-2);font-weight:500;list-style:none;display:inline-flex;gap:6px;align-items:center}
details.agent summary::-webkit-details-marker{display:none}
details.agent summary::before{content:"+";font-weight:700;width:12px}
details.agent[open] summary::before{content:"−"}
details.agent pre{margin:10px 0 0;background:var(--ink);color:oklch(94% 0.01 285);border-radius:10px;padding:14px;overflow:auto;font:400 .8rem/1.6 ui-monospace,SFMono-Regular,Menlo,monospace}

/* guides */
.guides{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.guides a{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:18px 20px;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);text-decoration:none;font-weight:600;transition:border-color .2s var(--ease)}
.guides a:hover{border-color:var(--line-2);color:var(--accent-ink)}
.guides a:hover .arrow{transform:translateX(3px)}

/* tips, faq, prose */
.tips{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;list-style:none;padding:0;margin:0}
.tips li{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:18px;color:var(--ink-2);font-size:.95rem}
.faq{display:grid;gap:10px;max-width:820px}
.faq details{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:4px 18px}
.faq summary{cursor:pointer;font:700 1.02rem/1.4 var(--display);padding:14px 0;list-style:none;display:flex;justify-content:space-between;gap:16px}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";color:var(--ink-3);font-weight:600}
.faq details[open] summary::after{content:"−"}
.faq .answer{padding:0 0 16px;color:var(--ink-2)}
.faq .answer a,.prose a{color:var(--accent-ink)}
.prose{max-width:72ch;padding:8px 0 40px}
.prose h1{margin:8px 0 18px}
.prose h2{margin:40px 0 12px;font-size:1.5rem}
.prose h3{margin:28px 0 8px}
.prose p,.prose li{color:var(--ink-2);text-wrap:pretty}
.prose p{margin:0 0 14px}
.prose ul,.prose ol{padding-left:22px;margin:0 0 16px}
.prose li{margin:6px 0}
.prose strong{color:var(--ink)}
.prose code{background:var(--sunk);border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:.88em}
.prose pre{background:var(--ink);color:oklch(94% 0.01 285);border-radius:12px;padding:16px;overflow:auto;font-size:.85rem;line-height:1.6;margin:0 0 18px}
.prose pre code{background:none;border:0;padding:0;color:inherit}
.prose blockquote{margin:0 0 16px;padding:14px 18px;background:var(--sunk);border-radius:10px}
.table{overflow-x:auto;margin:0 0 18px}
.prose table{border-collapse:collapse;width:100%;font-size:.92rem}
.prose th,.prose td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
.prose th{color:var(--ink);font-weight:600;background:var(--sunk)}

/* closing band + footer */
.band{background:var(--ink);color:#fff;border-radius:22px;padding:clamp(28px,4vw,48px);display:grid;grid-template-columns:1fr auto;gap:24px;align-items:center;margin:clamp(24px,4vw,48px) 0}
.band h2{color:#fff}
.band p{color:oklch(86% 0.02 285);margin-top:8px;max-width:56ch}
.band .btn{background:#fff;color:var(--ink)}
.band .btn:hover{background:oklch(95% 0.01 285)}
.foot{border-top:1px solid var(--line);padding:28px 0 44px;font-size:.88rem;color:var(--ink-3)}
.foot .wrap{display:flex;flex-wrap:wrap;gap:12px 28px;justify-content:space-between}
.foot a{color:var(--ink-2)}

@media (max-width:900px){
  .hero,.page-hero{grid-template-columns:1fr}
  .stack{max-width:520px;width:100%;margin-inline:auto}
  .page-hero .frame{max-width:320px;transform:none}
  .kinds{grid-template-columns:1fr 1fr}
  .kind,.kind:nth-child(-n+2){grid-column:span 1}
  .prompt{grid-template-columns:1fr}
  .prompt .spec{border-right:0;border-bottom:1px solid var(--line)}
  .spec dl{grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:14px 16px}
  .spec dl div{grid-template-columns:1fr;gap:2px}
  .spec dt{font-size:.78rem}
  .band{grid-template-columns:1fr}
}
@media (max-width:760px){
  .top .wrap{gap:12px;flex-wrap:wrap;padding:10px 0}
  .nav{order:3;width:calc(100% + 20px);margin:0 -20px 0 -10px;overflow-x:auto;scrollbar-width:none}
  .top .btn{margin-left:auto}
  .brand span{display:none}
}
@media (max-width:520px){
  .brand b{font-size:1rem}
  .top .btn{padding:8px 12px}
  .kinds{grid-template-columns:1fr}
  .tiles{grid-template-columns:1fr 1fr;gap:16px 12px}
  .prompt .spec,.prompt .main{padding:18px}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important}
}
"""

COPY_JS = """document.querySelectorAll('.copy').forEach(function(b){b.addEventListener('click',function(){var t=b.closest('.brief').querySelector('p').innerText;navigator.clipboard.writeText(t).then(function(){b.textContent='Copied';b.setAttribute('data-done','');setTimeout(function(){b.textContent='Copy';b.removeAttribute('data-done')},1600)})})});"""


def esc(text):
    return html.escape(text, quote=True)


def img_tag(src, alt, up, eager=False, sizes="(max-width: 900px) 100vw, 40vw"):
    if not src:
        return ""
    loading = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return f'<img src="{up}{src}" alt="{esc(alt)}" width="720" height="720" sizes="{sizes}" {loading}>'


def page_image(category, slug=None):
    return images.image_for(slug, category) if slug else images.image_for(category)


def theme_name(page):
    return page["title"].split(" Prompts")[0]


def page_html(path, title, description, body, breadcrumbs, jsonld=None, depth=0, current=None, og_image=None):
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
    crumbs = (
        '<nav class="crumbs wrap" aria-label="Breadcrumb">' + " / ".join(
            f'<a href="{up}{href}">{esc(name)}</a>' if i < len(breadcrumbs) - 1 else f'<span aria-current="page">{esc(name)}</span>'
            for i, (name, href) in enumerate(breadcrumbs)
        ) + "</nav>"
    ) if len(breadcrumbs) > 1 else ""
    current_attr = ' aria-current="page"'
    nav = "".join(
        f'<a href="{up}{c}/"{current_attr if c == current else ""}>{esc(NAV_LABELS[c])}</a>'
        for c in CATEGORY_ORDER
    )
    og = f'<meta property="og:image" content="{SITE}/{og_image}">' if og_image else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{url}">
{og}
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2326243f'/%3E%3Cpath d='M9 22l10-12 4 4-10 12H9z' fill='%23ff6b57'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>{CSS}</style>
{ld}
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="{up or './'}"><b>{SITE_NAME}</b><span>by InkChamps</span></a>
<nav class="nav" aria-label="Kinds of book">{nav}</nav>
<a class="btn btn-primary btn-sm" href="{inkchamps_link('github_pages', 'header')}">Make a book</a>
</div></header>
{crumbs}
<main>
{body}
</main>
<footer class="foot"><div class="wrap">
<span>Free prompts, licensed <a href="{REPO_URL}/blob/main/LICENSE">CC BY 4.0</a>. Sample pages made with InkChamps.</span>
<span><a href="{REPO_URL}">GitHub</a> · <a href="{up}prompts.json">prompts.json</a> · <a href="{inkchamps_link('github_pages', 'footer')}">InkChamps</a> · Updated {TODAY}</span>
</div></footer>
<script>{COPY_JS}</script>
</body>
</html>
"""


def band(up_label="Turn any prompt into a finished book", source="band"):
    return f"""<section class="wrap"><div class="band">
<div><h2>{esc(up_label)}</h2><p>InkChamps plans every page, draws it at the right line weight for the reader's age, and gives you a print-ready PDF for Amazon KDP, Etsy or home printing.</p></div>
<a class="btn" href="{inkchamps_link('github_pages', source)}">Open InkChamps <span class="arrow" aria-hidden="true">→</span></a>
</div></section>"""


def tile(category, page, up):
    src = page_image(category, page["slug"])
    ages = ages_of(page)
    meta = f'{len(page["prompts"])} prompts' + (f' · ages {", ".join(ages)}' if ages else "")
    return (f'<a class="tile" href="{up}{category}/{page["slug"]}/"><figure>{img_tag(src, theme_name(page), up, sizes="240px")}</figure>'
            f'<div><h3>{esc(theme_name(page))}</h3></div><p class="meta">{esc(meta)}</p></a>')


def html_prompt_page(category, page, pages):
    meta = S.CATEGORIES[category]
    up = "../../"
    src = page_image(category, page["slug"])
    ages = ages_of(page)
    chips = [f'{len(page["prompts"])} prompts', meta["label"]] + ([f'Ages {", ".join(ages)}'] if ages else [])
    parts = [f"""<section class="wrap page-hero">
<div><h1>{esc(page['title'])}</h1><p class="lead">{esc(page['intro'])}</p>
<ul class="chips">{''.join(f'<li>{esc(c)}</li>' for c in chips)}</ul>
<div class="howto"><span>Copy a brief into any AI tool, or open it in InkChamps already filled in.</span></div></div>
<div class="frame">{img_tag(src, f"Sample {meta['singular']} page made with InkChamps", up, eager=True)}</div>
</section>""", '<section class="wrap prompts" aria-label="Prompts">']
    items = []
    for i, prompt in enumerate(page["prompts"]):
        rows = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in settings(category, prompt))
        extra = prompt["fields"].get("additionalInstructions")
        link = make_link(category, prompt, page["slug"], i, "github_pages")
        parts.append(f"""<article class="prompt" id="prompt-{i + 1}">
<div class="spec"><span class="num">Prompt {i + 1} of {len(page['prompts'])}</span><h2>{esc(prompt['name'])}</h2><dl>{rows}</dl></div>
<div class="main">
<div class="brief"><div class="brief-bar"><span>Brief</span><button class="copy" type="button">Copy</button></div><p>{esc(main_text(category, prompt))}</p></div>
{f'<p class="extra"><b>Extra direction:</b> {esc(extra)}</p>' if extra else ''}
<p class="why"><b>Why it works.</b> {esc(prompt['why'])}</p>
<div class="actions"><a class="btn btn-primary" href="{esc(link)}">Make this {esc(meta['singular'])} <span class="arrow" aria-hidden="true">→</span></a></div>
<details class="agent"><summary>Exact settings for AI agents (InkChamps MCP)</summary><pre>{esc(json.dumps(mcp_call(category, prompt), indent=2, ensure_ascii=False))}</pre></details>
</div>
</article>""")
        items.append({"@type": "ListItem", "position": i + 1, "name": prompt["name"], "url": f"{SITE}/{category}/{page['slug']}/#prompt-{i + 1}"})
    parts.append("</section>")
    parts.append(f'<section class="wrap section"><div class="section-head"><h2>Tips for {esc(theme_name(page).lower())}</h2></div>'
                 '<ul class="tips">' + "".join(f"<li>{esc(t)}</li>" for t in page["tips"]) + "</ul></section>")
    parts.append(f'<section class="wrap section"><div class="section-head"><h2>More {esc(meta["label"].lower())} prompts</h2>'
                 f'<a class="more" href="../">All {esc(meta["label"].lower())} <span class="arrow" aria-hidden="true">→</span></a></div>'
                 '<div class="tiles">' + "".join(tile(category, p, up) for p in related(pages, page["slug"], 4)) + "</div></section>")
    parts.append(band(source=f"band-{page['slug']}"))
    jsonld = [{
        "@context": "https://schema.org", "@type": "ItemList", "name": page["title"],
        "description": page["metaDescription"], "numberOfItems": len(items), "itemListElement": items,
    }]
    return page_html(
        f"{category}/{page['slug']}/", f"{page['title']} | {SITE_NAME}", page["metaDescription"], "\n".join(parts),
        [(SITE_NAME, ""), (meta["label"], f"{category}/"), (theme_name(page), f"{category}/{page['slug']}/")],
        jsonld, depth=2, current=category, og_image=src,
    )


def html_category(category, pages):
    meta = S.CATEGORIES[category]
    up = "../"
    n = sum(len(p["prompts"]) for p in pages)
    description = f"{n} free AI prompts for {meta['label'].lower()} on {len(pages)} themes. {CATEGORY_BLURBS[category]}"
    src = page_image(category)
    body = f"""<section class="wrap page-hero">
<div><h1>{esc(meta['label'])} Prompts</h1><p class="lead">{esc(description)} Each one opens in InkChamps with one click and comes out as a print-ready PDF.</p>
<ul class="chips"><li>{n} prompts</li><li>{len(pages)} themes</li></ul></div>
<div class="frame">{img_tag(src, f"Sample {meta['singular']} page made with InkChamps", up, eager=True)}</div>
</section>
<section class="wrap section"><div class="tiles">{''.join(tile(category, p, up) for p in pages)}</div></section>
{band(source=f'band-{category}')}"""
    return page_html(f"{category}/", f"{meta['label']} Prompts ({n} free AI prompts) | {SITE_NAME}", description[:158],
                     body, [(SITE_NAME, ""), (meta["label"], f"{category}/")], depth=1, current=category, og_image=src)


def html_home(data):
    total = count_prompts(data)
    themes = sum(len(p) for p in data.values())
    description = (f"{total} free AI prompts for coloring books, story books, activity books and KDP covers. "
                   "Copy them or make the book in one click, print-ready for KDP and Etsy.")
    sheets = [("home-coloring", "A bold bunny coloring page"), ("home-story", "A picture book page of a boy riding a rocket"),
              ("home-activity", "A themed word search activity page")]
    stack = "".join(f'<div class="sheet">{img_tag(images.image_for(k), alt, "", eager=True, sizes="(max-width: 900px) 50vw, 25vw")}</div>' for k, alt in sheets)
    body = [f"""<section class="wrap hero">
<div>
<h1>AI coloring book prompts that become <span class="accent">finished books</span></h1>
<p class="lead">{total} tested briefs for coloring books, story books, activity books, educational books and KDP covers. Copy one into any AI tool, or open it in InkChamps and download a print-ready PDF.</p>
<div class="actions"><a class="btn btn-primary" href="#kinds">Browse the prompts <span class="arrow" aria-hidden="true">↓</span></a><a class="btn btn-ghost" href="{inkchamps_link('github_pages', 'home-hero')}">Make a book on InkChamps</a></div>
<ul class="facts"><li><b>{total}</b> prompts</li><li><b>{themes}</b> themes</li><li>Ages <b>3 to adult</b></li><li>Free, <b>CC BY 4.0</b></li></ul>
</div>
<div class="stack" aria-hidden="false">{stack}</div>
</section>""",
            '<section class="section" id="kinds"><div class="wrap"><div class="section-head"><div><h2>Pick a kind of book</h2>'
            '<p>Every prompt states its age band, page count, page size and style, because a book for a four-year-old and a book for an adult are drawn differently.</p></div></div>'
            '<div class="kinds">']
    for category, pages in data.items():
        meta = S.CATEGORIES[category]
        n = sum(len(p["prompts"]) for p in pages)
        body.append(f'<a class="kind" href="{category}/"><figure>{img_tag(page_image(category), meta["label"], "", sizes="(max-width: 520px) 100vw, 33vw")}</figure>'
                    f'<div class="body"><h3>{esc(meta["label"])}</h3><span class="count">{n} prompts · {len(pages)} themes</span><p>{esc(CATEGORY_BLURBS[category])}</p></div></a>')
    body.append("</div></div></section>")
    for category, pages in data.items():
        meta = S.CATEGORIES[category]
        shown = pages[:8]
        more = f'<a class="more" href="{category}/">All {len(pages)} themes <span class="arrow" aria-hidden="true">→</span></a>' if len(pages) > len(shown) else f'<a class="more" href="{category}/">Open <span class="arrow" aria-hidden="true">→</span></a>'
        body.append(f'<section class="section"><div class="wrap"><div class="section-head"><div><h2>{esc(meta["label"])}</h2><p>{esc(CATEGORY_BLURBS[category])}</p></div>{more}</div>'
                    f'<div class="tiles">{"".join(tile(category, p, "") for p in shown)}</div></div></section>')
    body.append('<section class="section"><div class="wrap"><div class="section-head"><h2>Guides</h2></div><ul class="guides">'
                + "".join(f'<li><a href="guides/{n}/"><span>{esc(t)}</span><span class="arrow" aria-hidden="true">→</span></a></li>' for n, t in GUIDES)
                + "</ul></div></section>")
    faq_items = "".join(
        f'<details><summary>{esc(q)}</summary><div class="answer">{mdlite.to_html(a.replace("guides/", SITE + "/guides/").replace(".md)", "/)"))}</div></details>'
        for q, a in FAQ)
    body.append(f'<section class="section"><div class="wrap"><div class="section-head"><h2>Questions</h2></div><div class="faq">{faq_items}</div></div></section>')
    body.append(band(source="band-home"))
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a)}}
        for q, a in FAQ]}
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": f"{SITE}/",
               "publisher": {"@type": "Organization", "name": "InkChamps", "url": INKCHAMPS}}
    return page_html("", f"{total} Free AI Coloring Book Prompts (KDP-ready) | Story & Activity Book Prompts", description,
                     "\n".join(body), [(SITE_NAME, "")], [site_ld, faq_ld], og_image=images.image_for("home-coloring"))


def html_guide(name, title):
    text = guide_markdown(name)
    first = re.search(r"^(?!#)(.+)$", text, re.M)
    description = re.sub(r"[*`\[\]]|\(http[^)]+\)", "", first.group(1))[:155] if first else title
    text = re.sub(r"\]\((?!http)([a-z0-9\-]+)\.md\)", r"](../\1/)", text)
    text = text.replace("](../prompts/", "](../../").replace("/README.md)", "/)")
    text = text.replace("](../prompts.json)", "](../../prompts.json)")
    text = re.sub(r"\]\(\.\./\.\./([a-z\-]+)/([a-z0-9\-]+)\.md\)", r"](../../\1/\2/)", text)
    body = f'<article class="wrap prose">{mdlite.to_html(text)}</article>{band(source="band-guide-" + name)}'
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
    if (ROOT / "assets" / "img").exists():
        shutil.copytree(ROOT / "assets" / "img", docs / "assets" / "img")
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

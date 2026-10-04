"""Builds the library from data/*.json.

    python3 tools/build.py          validate, then write README.md, prompts/,
                                    prompts.json, library.json and llms.txt
    python3 tools/build.py --check  validate only

Everything it writes is generated; edit data/ instead.
"""

import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import images  # noqa: E402
import schema as S  # noqa: E402
import validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPO = "gunjchhetri/ai-coloring-book-prompts"
REPO_URL = f"https://github.com/{REPO}"
INKCHAMPS = "https://inkchamps.com"
# The library's home: the README, every prompt page and llms.txt link here.
LIBRARY = f"{INKCHAMPS}/prompts"
CAMPAIGN = "ai-coloring-book-prompts"
SITE_NAME = "AI Coloring Book Prompts"


def _data_date():
    """When the prompts last changed (the last commit touching data/), not when
    the build ran: a date that moves on every rebuild is false freshness."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "data"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        return out or date.today().isoformat()
    except (OSError, subprocess.CalledProcessError):
        return date.today().isoformat()


DATA_DATE = _data_date()

# A theme's address on inkchamps.com drops the words its category already
# says: /prompts/coloring-books/dinosaur/, not .../dinosaur-coloring-book-prompts/.
URL_SUFFIXES = ("-story-coloring-book-prompts", "-coloring-book-prompts", "-story-book-prompts",
                "-activity-book-prompts", "-prompts")


def url_slug(slug):
    for suffix in URL_SUFFIXES:
        if slug.endswith(suffix):
            return slug[: -len(suffix)]
    return slug


def library_url(category, page=None):
    return f"{LIBRARY}/{category}/{url_slug(page['slug'])}/" if page else f"{LIBRARY}/{category}/"


def theme_name(page):
    return page["title"].split(" Prompts")[0]

CATEGORY_ORDER = list(S.CATEGORIES)


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

# (file in guides/, title, where llms.txt sends a reader): the guide's page on
# InkChamps, or its markdown in this repository when it has no other home.
GUIDES = [
    ("how-to-use-these-prompts", "How to use these prompts", f"{LIBRARY}/"),
    ("gemini-gem-and-custom-gpt", "Make a Gemini Gem or custom GPT that writes book prompts",
     f"{REPO_URL}/blob/main/guides/gemini-gem-and-custom-gpt.md"),
    ("ai-agents-mcp", "Order books from Claude, Cursor and other AI agents (MCP)",
     f"{INKCHAMPS}/blog/how-to-automate-coloring-book-creation-with-inkchamps-mcp/"),
    ("sell-ai-coloring-books-on-amazon-kdp", "Can you sell AI coloring books on Amazon KDP?",
     f"{INKCHAMPS}/blog/sell-ai-generated-coloring-books-amazon/"),
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
    # The prompts are the open data and stay here in full. The article around
    # them (intro, tips, sample pages) lives on InkChamps, so the two pages are
    # not copies of each other competing for the same searches.
    out = [f"# {theme_name(page)}: prompts", ""]
    src = images.image_for(page["slug"], category)
    if src:
        out += [f'<img src="../../{src}" alt="Sample {meta["singular"]} page made with InkChamps" width="280" align="right">', ""]
    out += [
        f"{len(page['prompts'])} prompts. The full page, with sample pages and tips, is in the "
        f"[InkChamps prompt library]({library_url(category, page)}). Each prompt below opens in InkChamps with one click; "
        "or copy the brief into any AI tool.",
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
            "<details><summary>Exact settings for AI agents (InkChamps MCP)</summary>",
            "",
            "```json",
            json.dumps(mcp_call(category, prompt), indent=2, ensure_ascii=False),
            "```",
            "",
            "</details>",
            "",
        ]
    out += ["## More prompts like these", ""]
    out += [f"- [{p['title']}]({p['slug']}.md)" for p in related(pages, page["slug"])]
    out += [
        "",
        "---",
        "",
        f"[All {meta['label'].lower()} prompts](README.md) · [Every prompt in the library](../../README.md) · "
        f"[This page on InkChamps]({library_url(category, page)}) · "
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


def md_readme(data):
    total = count_prompts(data)
    themes = sum(len(p) for p in data.values())
    out = [
        "# AI Coloring Book Prompts",
        "",
        f"**{total} validated AI prompts for coloring books, story books, activity books and KDP covers** — "
        f"{themes} themes, from dinosaurs and mandalas to ABC books, mazes and bedtime stories. "
        "Each one is a ready-made brief: copy it into any AI tool, or open it in "
        f"[InkChamps]({inkchamps_link('github', 'readme-intro')}) with one click and download a print-ready PDF "
        "for Amazon KDP, Etsy or home printing.",
        "",
        f"[**Browse the prompt library on InkChamps →**]({LIBRARY}/)  ·  [**Make a book on InkChamps →**]({inkchamps_link('github', 'readme-top')})",
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
    out += [f"- [{title}](guides/{name}.md)" for name, title, _ in GUIDES]
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


# ---------------------------------------------------------------- library.json (inkchamps.com/prompts)

def library_data(data):
    """Everything inkchamps.com needs to render /prompts/: pages, settings, briefs.

    The web app copies this file (ui: npm run sync:prompts) and builds its
    pages from it, so a prompt is only ever edited here.
    """
    def internal_make_path(category, prompt):
        params = {"tool": S.CATEGORIES[category]["website_tool"], "prompt": main_text(category, prompt)}
        return f"/dashboard/?{urlencode(params, quote_via=quote)}"

    categories = []
    for category, pages in data.items():
        meta = S.CATEGORIES[category]
        categories.append({
            "id": category, "label": meta["label"], "singular": meta["singular"], "blurb": CATEGORY_BLURBS[category],
            "image": f"/prompt-library/{category}.webp" if images.image_for(category) else None,
            "pages": [{
                "slug": page["slug"], "urlSlug": url_slug(page["slug"]), "title": page["title"], "theme": theme_name(page),
                "metaDescription": page["metaDescription"], "intro": page["intro"], "keywords": page["keywords"],
                "tips": page["tips"], "index": bool(page.get("index")), "ages": ages_of(page),
                "image": ("/prompt-library/" + images.image_for(page["slug"], category).split("/")[-1]) if images.image_for(page["slug"], category) else None,
                "prompts": [{
                    "name": prompt["name"], "brief": main_text(category, prompt),
                    "extra": prompt["fields"].get("additionalInstructions"), "why": prompt["why"],
                    "settings": [list(row) for row in settings(category, prompt)],
                    "makePath": internal_make_path(category, prompt), "mcp": mcp_call(category, prompt),
                } for prompt in page["prompts"]],
            } for page in pages],
        })
    return {"source": REPO_URL, "license": "CC-BY-4.0", "updated": DATA_DATE, "categories": categories}


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
                    "page": f"{library_url(category, page)}#prompt-{i + 1}",
                })
    prompts_json = json.dumps({"name": SITE_NAME, "license": "CC-BY-4.0", "source": REPO_URL, "count": len(records), "prompts": records}, indent=1, ensure_ascii=False)
    write(ROOT / "prompts.json", prompts_json + "\n")
    write(ROOT / "library.json", json.dumps(library_data(data), indent=1, ensure_ascii=False) + "\n")

    llms = [f"# {SITE_NAME}", "",
            f"> {len(records)} free, validated AI prompts for coloring books, story coloring books, illustrated children's picture books, activity books (mazes, word search, sudoku, tracing), educational coloring books and Amazon KDP covers. "
            f"Each prompt is a brief with age band, page count, page size and style, and opens in InkChamps ({INKCHAMPS}) with one click to make a print-ready PDF.",
            "", f"Browse: {LIBRARY}/ · Full data with exact InkChamps order settings: "
            f"https://raw.githubusercontent.com/{REPO}/main/prompts.json", ""]
    for category, pages in data.items():
        llms.append(f"## {S.CATEGORIES[category]['label']}")
        llms += [f"- [{p['title']}]({library_url(category, p)}): {p['metaDescription']}" for p in pages]
        llms.append("")
    llms.append("## Guides")
    llms += [f"- [{title}]({home})" for _, title, home in GUIDES]
    write(ROOT / "llms.txt", "\n".join(llms) + "\n")
    return len(records)


if __name__ == "__main__":
    problems = validate.check()
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} problem(s); nothing written.")
        sys.exit(1)
    if "--check" in sys.argv:
        print("All prompts valid.")
        sys.exit(0)
    print(f"Built {build()} prompts.")

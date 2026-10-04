"""Checks data/*.json against tools/schema.py. Imported by build.py.

Usage: python3 tools/validate.py [data/coloring-books.json ...]
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEXT_FIELDS = ("description", "storyPrompt", "storyText", "additionalInstructions", "title", "theme")


def _err(errors, where, message):
    errors.append(f"{where}: {message}")


def check_prompt(category, page_slug, index, prompt, errors):
    where = f"{category}/{page_slug} prompt {index + 1} ({prompt.get('name', '?')})"
    meta = S.CATEGORIES[category]
    fields = prompt.get("fields")

    for key in ("name", "why", "fields"):
        if not prompt.get(key):
            _err(errors, where, f"missing '{key}'")
    if not isinstance(fields, dict):
        return

    extra = set(prompt) - {"name", "why", "fields", "ageGroup", "numberOfPages", "pageSize", "highQuality"}
    if extra:
        _err(errors, where, f"unknown keys {sorted(extra)}")

    unknown = set(fields) - S.ALLOWED_FIELDS[category]
    if unknown:
        _err(errors, where, f"fields not taken by {meta['tool']}: {sorted(unknown)}")

    if category != "kdp-book-covers":
        if prompt.get("ageGroup") not in S.AGE_GROUPS:
            _err(errors, where, f"ageGroup must be one of {S.AGE_GROUPS}")
        pages = prompt.get("numberOfPages")
        if not isinstance(pages, int) or not S.MIN_PAGES <= pages <= S.MAX_PAGES:
            _err(errors, where, f"numberOfPages must be an integer {S.MIN_PAGES}-{S.MAX_PAGES}")
        if not isinstance(prompt.get("highQuality"), bool):
            _err(errors, where, "highQuality must be true or false")
    if prompt.get("pageSize", "8.5x11") not in S.PAGE_SIZES:
        _err(errors, where, f"pageSize must be one of {S.PAGE_SIZES}")

    main = fields.get(meta["main_field"]) or fields.get("description")
    if not main or len(main.strip()) < 40:
        _err(errors, where, f"needs a real brief in '{meta['main_field']}' (40+ characters)")

    for key in ("description", "storyPrompt", "additionalInstructions"):
        value = fields.get(key)
        if value is not None and len(value) > S.MAX_BRIEF_CHARS:
            _err(errors, where, f"{key} is {len(value)} characters; keep it under {S.MAX_BRIEF_CHARS}")

    # Style ids count too ("pixar_3d" is public text in the agent JSON), so
    # underscores split words before the whole-word match.
    blob = " ".join(str(fields.get(k, "")) for k in TEXT_FIELDS + ("style",)).lower()
    blob = (blob + " " + prompt.get("name", "").lower()).replace("_", " ")
    for term in S.BANNED_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", blob):
            _err(errors, where, f"mentions a brand or famous character: '{term}'")

    if category in ("coloring-books", "story-coloring-books"):
        if "style" in fields and fields["style"] not in S.COLORING_STYLES:
            _err(errors, where, f"style must be one of the coloring styles: {fields['style']}")
        if "complexity" in fields and fields["complexity"] not in S.COMPLEXITY:
            _err(errors, where, "complexity must be easy, medium or hard")
        if "pageCategory" in fields and fields["pageCategory"] not in S.PAGE_CATEGORIES:
            _err(errors, where, f"pageCategory must be one of {S.PAGE_CATEGORIES}")

    if category == "illustrated-story-books":
        if fields.get("style") not in S.ILLUSTRATION_STYLES:
            _err(errors, where, f"style (illustration) is required, one of {S.ILLUSTRATION_STYLES}")
        if "pageTemplate" in fields and fields["pageTemplate"] not in S.PAGE_TEMPLATES:
            _err(errors, where, f"pageTemplate must be one of {S.PAGE_TEMPLATES}")
        if fields.get("storyText") and fields.get("storyPrompt"):
            _err(errors, where, "use storyText or storyPrompt, not both")
        if fields.get("storyText") and fields.get("pageTemplate") == "full_page_image":
            _err(errors, where, "full_page_image cannot print your own storyText")

    if category == "activity-books":
        acts = fields.get("activities")
        if not isinstance(acts, list) or not acts:
            _err(errors, where, "activities is required")
            acts = []
        for act in acts:
            if act not in S.ACTIVITIES:
                _err(errors, where, f"unknown activity {act}")
        if len(set(acts)) != len(acts):
            _err(errors, where, "an activity is listed twice")
        ink = fields.get("inkByType") or {}
        need_ink = {a for a in acts if a not in S.INK_FIXED}
        if set(ink) != need_ink:
            _err(errors, where, f"inkByType must cover exactly {sorted(need_ink)}")
        for act, value in ink.items():
            if value not in S.INK_VALUES:
                _err(errors, where, f"inkByType.{act} must be color or black_and_white")
        mazes = fields.get("mazeStyles")
        if "maze_book" in acts:
            if not mazes or any(m not in S.MAZE_STYLES for m in mazes):
                _err(errors, where, f"mazeStyles is required with mazes, from {S.MAZE_STYLES}")
            elif prompt.get("ageGroup") == "3-6" and "round" in mazes:
                _err(errors, where, "round mazes are not drawn for ages 3-6")
        elif mazes:
            _err(errors, where, "mazeStyles only goes with maze_book")
        per = fields.get("pagesByType")
        if per is not None:
            if set(per) != set(acts):
                _err(errors, where, "pagesByType must name every chosen activity")
            elif sum(per.values()) != prompt.get("numberOfPages"):
                _err(errors, where, f"pagesByType adds up to {sum(per.values())}, not numberOfPages")

    if category == "kdp-book-covers":
        if fields.get("bookType") not in S.COVER_BOOK_TYPES:
            _err(errors, where, f"bookType must be one of {S.COVER_BOOK_TYPES}")
        sheets = fields.get("sheetCount")
        if not isinstance(sheets, int) or not 12 <= sheets <= 414:
            _err(errors, where, "sheetCount must be an integer 12-414")
        if "interiorPaperType" in fields and fields["interiorPaperType"] not in S.PAPER_TYPES:
            _err(errors, where, f"interiorPaperType must be one of {S.PAPER_TYPES}")


def check_file(path, errors, seen_slugs):
    data = json.loads(Path(path).read_text())
    category = data.get("category")
    if category not in S.CATEGORIES:
        _err(errors, path, f"category must be one of {list(S.CATEGORIES)}")
        return data
    if Path(path).stem != category:
        _err(errors, path, f"file name must be {category}.json")
    for page in data.get("pages", []):
        slug = page.get("slug", "?")
        where = f"{category}/{slug}"
        if not SLUG.match(slug):
            _err(errors, where, "slug must be lowercase-with-dashes")
        if slug in seen_slugs:
            _err(errors, where, "slug used twice")
        seen_slugs.add(slug)
        if "index" in page and not isinstance(page["index"], bool):
            _err(errors, where, "index must be true or false")
        for key in ("title", "metaDescription", "intro", "keywords", "tips", "prompts"):
            if not page.get(key):
                _err(errors, where, f"missing '{key}'")
        meta = page.get("metaDescription", "")
        if meta and not 90 <= len(meta) <= 160:
            _err(errors, where, f"metaDescription is {len(meta)} characters; aim for 120-155")
        if len(page.get("prompts", [])) < 2:
            _err(errors, where, "a page needs at least 2 prompts")
        names = [p.get("name") for p in page.get("prompts", [])]
        if len(set(names)) != len(names):
            _err(errors, where, "two prompts share a name")
        for i, prompt in enumerate(page.get("prompts", [])):
            check_prompt(category, slug, i, prompt, errors)
    return data


def check(paths=None):
    paths = paths or sorted(str(p) for p in (ROOT / "data").glob("*.json"))
    errors, seen = [], set()
    for path in paths:
        try:
            check_file(path, errors, seen)
        except json.JSONDecodeError as exc:
            _err(errors, path, f"invalid JSON: {exc}")
    return errors


if __name__ == "__main__":
    problems = check(sys.argv[1:] or None)
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} problem(s).")
        sys.exit(1)
    print("All prompts valid.")

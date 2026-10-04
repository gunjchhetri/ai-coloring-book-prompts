# Prompt data

Every prompt in this library lives here, one JSON file per kind of book. The
pages under `prompts/` and the website in `docs/` are generated from these files
by `python3 tools/build.py`. Never edit the generated files by hand.

## File shape

```json
{
  "category": "coloring-books",
  "pages": [
    {
      "slug": "dinosaur-coloring-book-prompts",
      "title": "Dinosaur Coloring Book Prompts",
      "metaDescription": "One sentence, 120-155 characters, that a searcher would click.",
      "intro": "Two to four sentences: who these books are for and why they sell or delight.",
      "keywords": ["dinosaur coloring book prompts", "dinosaur coloring pages for kids"],
      "tips": ["A short, specific tip for this theme.", "Another one."],
      "prompts": [
        {
          "name": "Friendly dinosaurs for preschoolers",
          "ageGroup": "3-6",
          "numberOfPages": 30,
          "pageSize": "8.5x11",
          "highQuality": false,
          "fields": {
            "description": "The brief, in plain words, as a customer would type it.",
            "style": "cute_animals",
            "complexity": "easy"
          },
          "why": "One sentence: who buys this and why."
        }
      ]
    }
  ]
}
```

`fields` holds exactly what the InkChamps order form (and its MCP tool) takes
for that kind of book. `tools/schema.py` lists the allowed fields and values
per category; `python3 tools/build.py --check` rejects anything else.

## Writing rules

These are what make a prompt work first time in InkChamps.

1. **Describe what is on the pages, not how to draw them.** InkChamps already
   makes clean, print-ready line art at the right line weight for the age. Say
   which subjects, scenes, moments and mood the book has. Leave out drawing
   rules ("thick lines", "no shading", "white background", "high resolution").
2. **Be concrete.** "A stegosaurus watering a vegetable garden" beats "cute
   dinosaurs doing things". Name real animals, places, objects and actions.
3. **One item per page, when the book is a list.** An alphabet, numbers, shapes,
   habits, feelings or a named set of animals is one item per page. List them
   all in the brief and set `numberOfPages` to the count exactly. Use
   `pageCategory: "concept"` (alphabet, numbers, shapes, colors) or
   `"instructional"` (habits, rules, steps, feelings) for these.
4. **Pick the age honestly.** The four bands are `3-6`, `6-9`, `9-13` and
   `13+` (teens and adults). The band changes line weight, detail and
   background density, so a toddler book and an adult book differ.
5. **No brands, famous characters or real people.** Nothing that belongs to a
   film, game, toy or show. Original characters only; it is what makes a book
   safe to sell on Amazon KDP or Etsy.
6. **Words on pages are opt-in.** Coloring pages carry no words unless the book
   is a concept or instructional book (then each page gets its caption) or a
   story coloring book (a line or two of story per page). Don't ask for text
   inside the pictures of a plain coloring book.
7. **Stay under 600 characters** for `description`, `storyPrompt` and
   `additionalInstructions`, so the brief fits the order form and the
   one-click link.
8. **Give a real reason.** `why` names the buyer (KDP seller, Etsy shop,
   parent, teacher, homeschooler, adult colorist) and why this book works.

## Per category

| File | Tool | Notes |
|---|---|---|
| `coloring-books.json` | `create_coloring_book` | `style` from the coloring styles, `complexity` easy/medium/hard, `pageCategory` for list books |
| `story-coloring-books.json` | `create_story_coloring_book` | the description is the story's premise; each page carries a line or two of story |
| `illustrated-story-books.json` | `create_illustrated_story_book` | `style` (illustration style) is required; give `storyPrompt` (a premise InkChamps writes) and a `pageTemplate` |
| `activity-books.json` | `create_activity_book` | `activities` in order; `inkByType` for every activity except `coloring_book` and `abc_book`; `mazeStyles` only with mazes (no `round` for 3-6); `pagesByType` must add up to `numberOfPages` |
| `educational-coloring-books.json` | `create_educational_coloring_book` | the description is what the book teaches, one idea per page |
| `kdp-book-covers.json` | `create_cover_photo` | `bookType`, `sheetCount` (sheets of paper, 12-414), the description is the cover art and mood |

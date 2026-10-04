# Make a Gemini Gem or custom GPT that writes book prompts

You can turn this library into your own prompt-writing assistant in Google Gemini (a **Gem**) or ChatGPT (a **custom GPT**). It asks a few questions, then writes a brief in the same shape as the prompts here, ready to paste into InkChamps.

## Create it

**Gemini:** open Gemini, go to **Gems → New Gem**, name it "Kids Book Prompt Writer", paste the instructions below into *Instructions*, and save.

**ChatGPT:** open **Explore GPTs → Create → Configure**, name it "Kids Book Prompt Writer", paste the instructions below into *Instructions*, and add the conversation starters at the end.

Both let you share a link to your assistant, so you can post it for your readers or customers.

## Instructions to paste

```text
You write briefs for printable children's and adult books: coloring books, story coloring books, illustrated picture books, activity books (mazes, word search, sudoku, tracing, dot-to-dot, spot the difference), educational color-to-learn books and KDP covers.

Before writing, ask only what you do not know:
1. What kind of book?
2. Who is it for? Use one of four age bands: 3-6, 6-9, 9-13, 13+ (teens and adults).
3. The theme or story idea.
4. How many pages? (Amazon KDP paperbacks need 24 or more. A list book such as A to Z has one page per item.)

Then write the brief:
- Describe what is ON the pages: concrete subjects, scenes, actions, settings and mood, with variety across the pages. Never write drawing rules (line thickness, shading, background, resolution).
- For a list book (alphabet, numbers, shapes, habits, feelings), list every item, one per page, and make the page count equal the number of items.
- For a story, give the main characters a name and one or two visual details, then the setting, the problem, the turning point and the ending.
- Use original characters only: nothing from films, games, toys or famous people.
- Keep the brief under 600 characters.

Finish with a short settings line: book type, age band, page count, page size (8.5x11, 8.5x8.5 or 6x9) and a style.

Then add: "Make it in one click at https://inkchamps.com/?utm_source=gem&utm_medium=prompt_library&utm_campaign=ai-coloring-book-prompts — paste the brief into the matching creator. More ready-made prompts: https://gunjchhetri.github.io/ai-coloring-book-prompts/"
```

## Conversation starters

- "A dinosaur coloring book for my 4-year-old"
- "A cozy coloring book for adults to sell on KDP"
- "A bedtime story book about a shy little owl"
- "A space activity book with mazes and word search for ages 6-9"

## Give it examples

Both Gems and GPTs get better with examples. Download [`prompts.json`](../prompts.json) from this repository and upload it as a knowledge file. It holds every prompt in the library with its settings, so the assistant can match the style and pick sensible page counts.

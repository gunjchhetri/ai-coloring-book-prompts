"""The rules every prompt in data/ must follow.

They mirror what InkChamps itself accepts (its public `list_book_types`
catalogue), so a prompt that passes here opens in the InkChamps creator and
goes through as an order unchanged. Run `python3 tools/build.py --check`.
"""

AGE_GROUPS = ["3-6", "6-9", "9-13", "13+"]
PAGE_SIZES = ["8.5x11", "8.5x8.5", "6x9"]
MIN_PAGES, MAX_PAGES = 2, 120
MAX_BRIEF_CHARS = 600
MAX_INSTRUCTION_CHARS = 600

COLORING_STYLES = [
    "cute_animals", "cute_birds", "cute_insects", "mandala_animal", "mandala_sea",
    "mandala_birds", "mandala_abstract", "jungle_adventure", "story",
    "anxiety_motivation", "food_fun", "universe_space", "anime_characters",
    "inspirational", "mythology", "christmas", "fairy_tale", "general_coloring",
]
COMPLEXITY = ["easy", "medium", "hard"]
PAGE_CATEGORIES = ["auto", "thematic", "narrative", "instructional", "concept"]
ILLUSTRATION_STYLES = [
    "pixar_3d", "hand_drawn_2d", "ghibli_painterly", "anime", "chibi_kawaii",
    "comic_book", "disney_storybook", "colored_pencil_sketch", "chibi_art",
    "paper_cutout_collage",
]
ILLUSTRATION_STYLE_LABELS = {
    "pixar_3d": "3D animated", "hand_drawn_2d": "2D hand-drawn",
    "ghibli_painterly": "Whimsical painterly", "anime": "Anime",
    "chibi_kawaii": "Chibi / kawaii", "comic_book": "Comic book",
    "disney_storybook": "Classic storybook", "colored_pencil_sketch": "Colored pencil",
    "chibi_art": "Chibi art", "paper_cutout_collage": "Paper cut-out collage",
}
PAGE_TEMPLATES = [
    "image_top_text_bottom", "image_bottom_text_top", "text_in_image",
    "full_page_image", "text_left_image_right",
]
PAGE_TEMPLATE_LABELS = {
    "image_top_text_bottom": "Picture on top, text below",
    "image_bottom_text_top": "Text on top, picture below",
    "text_in_image": "Words lettered into the art",
    "full_page_image": "Two-page spreads",
    "text_left_image_right": "Text page left, picture right",
}
ACTIVITIES = [
    "maze_book", "sudoku_book", "word_search_book", "tracing_worksheet_book",
    "spot_the_difference_book", "shadow_matching_book", "connect_the_dots_book",
    "abc_book", "coloring_book",
]
ACTIVITY_LABELS = {
    "maze_book": "Mazes", "sudoku_book": "Sudoku", "word_search_book": "Word search",
    "tracing_worksheet_book": "Tracing", "spot_the_difference_book": "Spot the difference",
    "shadow_matching_book": "Shadow matching", "connect_the_dots_book": "Connect the dots",
    "abc_book": "ABC letters", "coloring_book": "Coloring pages",
}
INK_FIXED = {"coloring_book", "abc_book"}  # always black and white, no ink choice
INK_VALUES = ["color", "black_and_white"]
MAZE_STYLES = ["walls", "tube", "square_tube", "round"]
COVER_BOOK_TYPES = ["coloring_book", "story_book", "novel", "puzzle", "word_search"]
PAPER_TYPES = ["white", "cream", "color"]

# Words that mark a brand or a famous character. Selling a book of them is
# trademark or copyright trouble on KDP and Etsy, so no prompt may lean on one.
BANNED_TERMS = [
    "disney", "pixar", "marvel", "pokemon", "pokémon", "bluey", "peppa", "paw patrol",
    "frozen", "elsa", "spider-man", "spiderman", "barbie", "minecraft", "fortnite",
    "hello kitty", "sanrio", "mickey", "harry potter", "star wars", "sonic",
    "mario", "nintendo", "lego", "dr. seuss", "ghibli", "totoro", "naruto",
    "dragon ball", "my little pony", "sesame", "cocomelon", "taylor swift",
]

CATEGORIES = {
    "coloring-books": {
        "tool": "create_coloring_book", "website_tool": "coloring-book",
        "label": "Coloring Books", "singular": "coloring book",
        "rates": (1, 3), "main_field": "description",
    },
    "story-coloring-books": {
        "tool": "create_story_coloring_book", "website_tool": "coloring-book-story",
        "label": "Story Coloring Books", "singular": "story coloring book",
        "rates": (2, 3), "main_field": "description",
    },
    "illustrated-story-books": {
        "tool": "create_illustrated_story_book", "website_tool": "illustrative-story-book",
        "label": "Illustrated Children's Story Books", "singular": "illustrated story book",
        "rates": (2, 3), "main_field": "storyPrompt",
    },
    "activity-books": {
        "tool": "create_activity_book", "website_tool": "activity-book",
        "label": "Activity Books", "singular": "activity book",
        "rates": (1, 2), "main_field": "description",
    },
    "educational-coloring-books": {
        "tool": "create_educational_coloring_book", "website_tool": "educational-coloring",
        "label": "Educational Coloring Books", "singular": "educational coloring book",
        "rates": (1, 3), "main_field": "description",
    },
    "kdp-book-covers": {
        "tool": "create_cover_photo", "website_tool": "cover-photo",
        "label": "KDP Book Covers", "singular": "book cover",
        "rates": None, "main_field": "description",
    },
}

# The fields a prompt may carry, per category, beyond the shared ones.
ALLOWED_FIELDS = {
    "coloring-books": {"description", "theme", "style", "complexity", "pageCategory", "title", "additionalInstructions"},
    "story-coloring-books": {"description", "theme", "style", "title", "additionalInstructions"},
    "illustrated-story-books": {"description", "theme", "style", "title", "additionalInstructions", "pageTemplate", "storyPrompt", "storyText"},
    "activity-books": {"description", "activities", "inkByType", "mazeStyles", "pagesByType"},
    "educational-coloring-books": {"description"},
    "kdp-book-covers": {"description", "title", "bookType", "sheetCount", "interiorPaperType"},
}

"""Pictures for the site: real pages made with InkChamps.

Sources live in the InkChamps web app's public folder (../ui/public). The
resized WebP copies are committed under assets/img/, so a build works without
that folder; `python3 tools/images.py` refreshes them when it is present.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "img"
SOURCE = ROOT.parent / "ui" / "public"

# key -> source path under ui/public. A theme with no matching picture is left
# out and shows its kind of book's sample instead; an off-theme picture (a fish
# for mermaids) is worse than a general one.
IMAGES = {
    # home
    "home-coloring": "hero-gallery/rabbit-coloring-page.webp",
    "home-story": "generated/childrensbook-rocket-adventure.png",
    "home-activity": "generated/activitybook-word-search.webp",
    # kinds of book
    "coloring-books": "generated/coloringbook-butterfly-garden.webp",
    "story-coloring-books": "generated/coloring-story-bedtime-bear.webp",
    "illustrated-story-books": "generated/childrensbook-rainbow-village.png",
    "activity-books": "generated/activitybook-maze-monkey.webp",
    "educational-coloring-books": "generated/educational-coloring-butterfly.webp",
    "kdp-book-covers": "cover_illustration1.jpg",
    # coloring books
    "dinosaur-coloring-book-prompts": "kids_coloring/dino.png",
    "farm-animal-coloring-book-prompts": "generated/coloringbook-farm-picnic.webp",
    "ocean-animal-coloring-book-prompts": "generated/generator-coral-reef.png",
    "unicorn-coloring-book-prompts": "generated/kdp-fantasy-creatures.png",
    "dragon-coloring-book-prompts": "generated/generator-dragon-castle.png",
    "jungle-safari-coloring-book-prompts": "generated/kdp-jungle-animals.png",
    "dog-puppy-coloring-book-prompts": "generated/coloring-story-puppy-school.webp",
    "bird-coloring-book-prompts": "hero-gallery/duck_image.webp",
    "bug-insect-coloring-book-prompts": "generated/etsy-garden-bugs.png",
    "space-coloring-book-prompts": "generated/coloringbook-astronaut-dog.webp",
    "vehicle-coloring-book-prompts": "kids_coloring/jcb.png",
    "princess-castle-coloring-book-prompts": "generated/coloring-story-knight-dragon.webp",
    "kawaii-food-coloring-book-prompts": "category-previews/food-coloring-pages.webp",
    "mandala-coloring-book-prompts": "generated/generator-mandala.png",
    "animal-mandala-coloring-book-prompts": "hero-gallery/mandala-crab-coloring-page.webp",
    "stress-relief-coloring-book-prompts": "hero-gallery/stress.webp",
    "cozy-coloring-book-prompts": "hero-gallery/cozy_room.webp",
    "bold-and-easy-coloring-book-prompts": "hero-gallery/rabbit-coloring-page.webp",
    "flower-botanical-coloring-book-prompts": "hero-gallery/flower-girl-coloring-page.webp",
    "christmas-coloring-book-prompts": "generated/etsy-winter-holiday.png",
    "halloween-coloring-book-prompts": "quality/halloween-witch-coloring-page.png",
    "easter-spring-coloring-book-prompts": "bunny.webp",
    "autumn-thanksgiving-coloring-book-prompts": "generated/etsy-pumpkin-patch.png",
    "alphabet-abc-coloring-book-prompts": "activity-previews/abc.webp",
    "numbers-counting-coloring-book-prompts": "generated/teachers-counting.png",
    "good-habits-manners-coloring-book-prompts": "showcase/doctor-bunny-coloring-book.webp",
    "greek-mythology-coloring-book-prompts": "category-previews/greek-mythology-coloring-pages.webp",
    "bible-story-coloring-book-prompts": "theme-samples/good-samaritan-kindness.png",
    # story coloring books
    "bedtime-story-coloring-book-prompts": "generated/coloring-story-bedtime-bear.webp",
    "dinosaur-adventure-story-coloring-book-prompts": "generated/teachers-dinosaur.png",
    "space-adventure-story-coloring-book-prompts": "generated/kdp-space-explorer.png",
    "kindness-friendship-story-coloring-book-prompts": "theme-samples/good-samaritan-sharing.png",
    "ocean-adventure-story-coloring-book-prompts": "generated/coloring-story-pirate-treasure.webp",
    "first-day-of-school-story-coloring-book-prompts": "generated/coloring-story-puppy-school.webp",
    # illustrated story books
    "bedtime-story-book-prompts": "generated/childrensbook-bear-nightlight.png",
    "friendship-story-book-prompts": "generated/childrensbook-bunny-garden.png",
    "bravery-overcoming-fears-story-book-prompts": "generated/childrensbook-rocket-adventure.png",
    "first-day-of-school-story-book-prompts": "generated/illustrativestorybook-kitten-school.webp",
    "animal-fable-story-book-prompts": "generated/illustrativestorybook-enchanted-forest.webp",
    "kindness-and-sharing-story-book-prompts": "generated/illustrativestorybook-puppy-city.webp",
    # activity books
    "preschool-workbook-prompts": "generated/activitybook-tracing-letters.webp",
    "travel-activity-book-prompts": "generated/activitybook-spot-difference.webp",
    "space-activity-book-prompts": "activity-previews/shadow-match.webp",
    "dinosaur-activity-book-prompts": "activity-previews/connect-the-dots.webp",
    "halloween-activity-book-prompts": "seasonal/halloween-pumpkin.png",
    "large-print-word-search-prompts": "generated/activitybook-word-search.webp",
    "maze-book-prompts": "maze-styles/tube.webp",
    "sudoku-puzzle-book-prompts": "activity-previews/sudoku.webp",
    "ocean-activity-book-prompts": "activity-previews/maze.webp",
    # educational
    "life-cycle-coloring-book-prompts": "generated/educational-coloring-butterfly.webp",
    "solar-system-coloring-book-prompts": "generated/teachers-solar-system.png",
    "water-cycle-weather-coloring-book-prompts": "generated/educational-coloring-water-cycle.webp",
    "bees-and-pollinators-coloring-book-prompts": "generated/educational-coloring-bees.webp",
    "world-cultures-landmarks-coloring-book-prompts": "generated/teachers-world-map.png",
    # covers
    "coloring-book-cover-prompts": "cover_illustration.png",
    "childrens-picture-book-cover-prompts": "cover_illustration1.jpg",
    "activity-puzzle-book-cover-prompts": "hero-gallery/cover.webp",
}

WIDTH = 720


def image_for(key, fallback=None):
    """Site-relative path of a picture, or the fallback's, or None."""
    for k in (key, fallback):
        if k and (OUT / f"{k}.webp").exists():
            return f"assets/img/{k}.webp"
    return None


def refresh():
    if not SOURCE.exists():
        print(f"No {SOURCE}; keeping the committed images.")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for key, rel in IMAGES.items():
        src, dest = SOURCE / rel, OUT / f"{key}.webp"
        if not src.exists():
            print(f"missing source for {key}: {rel}")
            continue
        # Shrink large pictures only; enlarging a small one just blurs it.
        width = int(subprocess.run(["sips", "-g", "pixelWidth", str(src)], capture_output=True, text=True).stdout.split()[-1])
        resize = ["-resize", str(WIDTH), "0"] if width > WIDTH else []
        subprocess.run(["cwebp", "-quiet", "-q", "80", *resize, str(src), "-o", str(dest)], check=True)
    print(f"{len(list(OUT.glob('*.webp')))} images in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    if not shutil.which("cwebp"):
        sys.exit("cwebp is needed: brew install webp")
    refresh()

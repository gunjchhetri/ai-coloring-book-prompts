# Contributing

Thank you for helping make better book prompts.

1. Read [`data/README.md`](data/README.md): the file shape and the eight writing rules.
2. Add your prompt to the right file in `data/` (or a new theme page with at least two prompts).
3. Run `python3 tools/build.py`. It checks every prompt against what InkChamps accepts (ages, page counts, styles, activities) and rebuilds `prompts/`, `README.md`, `prompts.json`, `library.json` and `llms.txt`. No dependencies beyond Python 3.
4. Open a pull request with the data change and the rebuilt files.

Good prompts are concrete, age-appropriate and original: no characters, logos or names from films, games, toys or shows, and no real people. The build rejects the common ones.

Have an idea but no time to write it? [Open a prompt request](../../issues/new?template=prompt-request.md).

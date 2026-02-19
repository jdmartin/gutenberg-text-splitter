1. Deal with sample preview for elements like `<hr>` that are self-closing (get siblings instead)
    - Partially addressed: `batch-splitter.py --analyze` now shows sibling content size for non-container elements and collapses `<hr>` display to a single summary line.
2. ~~Texts like [this](https://www.gutenberg.org/files/68033/68033-h/68033-h.htm) have busted HTML (divs marked chapter that are just headings, and the siblings are the meat). Handle it.~~ Handled.
    - ~~Also busted: [this guy](https://www.gutenberg.org/files/68034/68034-h/68034-h.htm) (need siblings from `<hr>` elements to get chapters...)~~
    - Further addressed: `batch-splitter.py` adds `--boundary-mode` flag with `auto`/`container`/`sibling` options. Auto-detection samples element text length and switches to sibling mode if average < 100 chars. Tested against PG #41445 (Frankenstein 1818, thin wrapper divs) and PG #84 (Frankenstein, full container divs).
3. Create a more interactive processing mode for ornery texts.
    - Case in point, [this guy](https://www.gutenberg.org/files/64317/64317-h/64317-h.htm). Chapters are marked by divs, but they're sequentially numbered.  Maybe user to tell analyzer which attributes to not use?
    - Partially addressed: `batch-splitter.py --analyze` filters out known non-structural Gutenberg CSS classes (e.g., `dsdnote`, `dtablebox`, `dpoemctr`, `padtopa`) using heuristics and an explicit skip list. Caps display at top 5 options to reduce noise.
4. Maybe find a way to allow user to browse bookshelves / other books that are in a given book's bookshelf?
5. ~~Add batch/corpus processing mode.~~ Done.
    - `batch-splitter.py --config corpus.yaml` processes multiple texts from a single YAML config. See `corpus_example.yaml` for template and `shelley_lovelace.yaml` for a working 15-text corpus.
6. ~~Add search and download.~~ Done.
    - `batch-splitter.py --search` queries the Gutenberg catalog (auto-downloaded, weekly refresh). `--download ID` fetches HTML with fallback across four Gutenberg URL patterns.
7. ~~Add `--analyze` mode.~~ Done.
    - Non-interactive alternative to splitter.py's explore workflow. Scans HTML structure, ranks candidate elements, shows content sizes, auto-detects offset, outputs a ready-to-run command.
8. ~~Add `--prefix` for pipeline-compatible naming.~~ Done.
    - Controls both output folder and file naming (e.g., `--prefix "1818-ENG18180--Shelley_Mary"` produces `1818-ENG18180--Shelley_Mary-chapter_1` etc.)
9. ~~Add `--limit` flag.~~ Done.
    - Stops processing after N chapters. Useful for excluding editorial apparatus (footnotes, appendices) that shares the same element structure as novel chapters.
# gutenberg-text-splitter

### What is this?

This program splits HTML books from [Project Gutenberg](https://www.gutenberg.org/) (and other sources) into individual chapter files for further processing. It offers two interfaces:

- **`splitter.py`** -- Interactive menu-driven interface. Good for exploring unfamiliar texts.
- **`batch-splitter.py`** -- Command-line interface with search, download, analyze, and batch processing modes. Recommended for reproducible workflows and corpus building.

Both produce identical output: one file per chapter, in either plain text or TEI XML format.

### Quick start

```bash
# Install
git clone https://github.com/jdmartin/gutenberg-text-splitter.git
cd gutenberg-text-splitter
poetry install    # or: pip install -r requirements.txt

# Find a text
poetry run python batch-splitter.py --search --search-title "Frankenstein" --search-author "Shelley"

# Download it
poetry run python batch-splitter.py --download 41445 --save-as frankenstein_1818.html

# See how it's structured
poetry run python batch-splitter.py --analyze input/frankenstein_1818.html

# Split it
poetry run python batch-splitter.py --file input/frankenstein_1818.html --elem div --attr chapter --offset 3 --tei
```

### batch-splitter.py modes

**Search** the Gutenberg catalog (auto-downloads on first use):

```bash
poetry run python batch-splitter.py --search --search-title "Paradise Lost"
poetry run python batch-splitter.py --search --search-author "Babbage"
poetry run python batch-splitter.py --search --search-subject "Gothic fiction"
```

**Download** a text by Gutenberg ID:

```bash
poetry run python batch-splitter.py --download 41445 --save-as frankenstein_1818.html
```

**Analyze** an HTML file to determine splitting parameters:

```bash
poetry run python batch-splitter.py --analyze input/frankenstein_1818.html
```

This scans the HTML structure and shows candidate elements for chapter detection, ranked by likelihood. For each option it displays sample text, content size, and auto-detection of container vs. boundary-marker mode. It suggests a ready-to-run command with auto-detected offset.

**Split** a single file:

```bash
poetry run python batch-splitter.py --file input/frankenstein_1818.html \
  --elem div --attr chapter --offset 3 --year 1818 --tei \
  --title "Frankenstein" --author "Shelley, Mary (1797-1851)" \
  --publisher "Lackington et al." --location "London" \
  --div-type chapter --prefix "1818-ENG18180--Shelley_Mary"
```

**Batch process** a corpus from a YAML config:

```bash
poetry run python batch-splitter.py --config shelley_lovelace.yaml
```

### Splitting options

| Flag | Description |
|------|-------------|
| `--elem` | HTML element marking chapter boundaries (e.g., `div`, `h2`, `hr`) |
| `--attr` | Optional class or ID to filter elements (e.g., `chapter`) |
| `--offset` | Number of matching elements to skip (front matter, TOCs, etc.) |
| `--limit` | Maximum number of chapters to write (0 = no limit) |
| `--boundary-mode` | `auto` (default), `container`, or `sibling` (see below) |
| `--prefix` | Controls output folder and file naming for pipeline compatibility |
| `--year` | Publication year, included in output directory name |
| `--tei` | Output TEI XML instead of plain text |
| `--end-marker` | Text signaling end of content (default: `PROJECT GUTENBERG EBOOK`) |

### TEI metadata flags

When using `--tei`, these populate the TEI header:

| Flag | Description |
|------|-------------|
| `--title` | Work title |
| `--author` | Author name |
| `--publisher` | Publisher name |
| `--location` | Place of publication |
| `--div-type` | TEI div type: `chapter`, `section`, `book`, `note`, etc. |

### Container vs. sibling mode

Gutenberg HTML uses two patterns for chapter markup:

**Container mode** -- chapter content is inside the matched element:
```html
<div class="chapter">
  <h3>CHAPTER I</h3>
  <p>It was a dark and stormy night...</p>
</div>
```

**Sibling mode** -- the matched element is a boundary marker, content follows as siblings:
```html
<h2>CHAPTER I</h2>
<p>It was a dark and stormy night...</p>
<p>The rain fell in torrents...</p>
<h2>CHAPTER II</h2>
```

By default (`--boundary-mode auto`), the splitter samples element text length and picks the right mode. Use `--boundary-mode container` or `--boundary-mode sibling` to override.

### YAML corpus config

For reproducible corpus building, define all texts in a YAML file:

```yaml
corpus_name: my-corpus
output_format: tei
output_dir: output

texts:
  - file: input/frankenstein_1818.html
    elem: div
    attr: chapter
    offset: 3
    year: "1818"
    boundary_mode: sibling
    prefix: "1818-ENG18180--Shelley_Mary"
    tei:
      title: "Frankenstein; Or, The Modern Prometheus"
      author: "Shelley, Mary Wollstonecraft (1797-1851)"
      publisher: "Lackington, Hughes, Harding, Mavor and Jones"
      location: "London"
      div_type: chapter

  - file: input/paradise_lost.html
    elem: div
    attr: chapter
    offset: 1
    year: "1667"
    prefix: "1667-ENG16670--Milton_John"
    tei:
      title: "Paradise Lost"
      author: "Milton, John (1608-1674)"
      publisher: "Samuel Simmons"
      location: "London"
      div_type: book
```

See `corpus_example.yaml` for a documented template and `shelley_lovelace.yaml` for a working 15-text corpus config.

### The prefix flag and pipeline compatibility

The `--prefix` flag controls both output folder and file naming. This is useful for matching downstream pipeline conventions. For example:

```bash
--prefix "1818-ENG18180--Shelley_Mary"
```

Produces:
```
output/1818-ENG18180--Shelley_Mary/
  1818-ENG18180--Shelley_Mary-chapter_1
  1818-ENG18180--Shelley_Mary-chapter_2
  ...
```

### Interactive splitter (splitter.py)

The original interactive interface is still available:

```bash
poetry run python splitter.py
```

This provides a menu-driven workflow for exploring texts, previewing chapter boundaries, and processing files. See the in-app help for details.

### Assumptions

The code works best with well-formed HTML. Gutenberg texts vary in markup quality, so the `--analyze` mode is designed to help you find the right splitting parameters for each text. Typical issues include:

- Thin wrapper divs (older Gutenberg transcriptions use `<div class="chapter"><h3>heading</h3></div>` with content as siblings rather than children)
- Formatting-class divs that look structural but aren't (e.g., `dsdnote`, `dtablebox`, `dpoemctr`)
- Inconsistent front matter that requires offset tuning
- Editorial apparatus mixed in with novel content (use `--limit` to exclude)

### A note on saving files

In general, browsers' "save webpage as" feature can cause character encoding issues. If downloading manually, right-click, view page source, and copy-paste the entire contents into `input/somefile.html`. Or use the built-in download:

```bash
poetry run python batch-splitter.py --download 41445 --save-as frankenstein_1818.html
```
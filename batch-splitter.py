#!/usr/bin/env python
# IMPORTANT: Run this script with `poetry run python3 batch-splitter.py` (not bare python3).
"""
batch-splitter.py - Non-interactive batch processing for gutenberg-text-splitter.

Processes one or more HTML texts into chapter files (plain text or TEI XML)
without the interactive menu. Supports single-file CLI mode and multi-file
corpus mode via YAML config.

Usage:
    # Single file, plain text output:
    python3 batch-splitter.py --file input/frankenstein.html --elem h3

    # Single file, TEI output with metadata:
    python3 batch-splitter.py --file input/frankenstein.html --elem h3 --tei \\
        --title "Frankenstein" --author "Mary Shelley" --year 1818

    # Corpus mode (multiple files from config):
    python3 batch-splitter.py --config corpus.yaml
"""

import argparse
import os
import shutil
import sys

from bs4 import BeautifulSoup, NavigableString, Tag
from rich import print
from rich.console import Console
from rich.table import Table

import re

console = Console()

# Default threshold for warning about suspiciously small sections.
# Sections below this word count are flagged as possible content loss.
DEFAULT_WARN_WORDS = 100


def read_file(filepath):
    """Read a text file, trying UTF-8 first, then Latin-1 fallback."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        console.print(f"  [yellow]UTF-8 failed for {filepath}, trying Latin-1...[/yellow]")
        with open(filepath, "r", encoding="latin-1") as f:
            return f.read()


# ---------------------------------------------------------------------------
# TEI generation helpers
# ---------------------------------------------------------------------------

def make_tei_head(title, author, publisher, location, year, div_type, div_n):
    """Build a TEI Simple header string."""
    return (
        '<?xml-model href="https://raw.githubusercontent.com/TEIC/TEI-Simple/master/teisimple.rng"'
        ' type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">'
        "<teiHeader>"
        "<fileDesc>"
        "<titleStmt>"
        f"<title>{title}</title>"
        f"<author>{author}</author>"
        "</titleStmt>"
        "<publicationStmt>"
        f"<publisher>{publisher}</publisher>"
        f"<pubPlace>{location}</pubPlace>"
        f"<date>{year}</date>"
        "</publicationStmt>"
        "<sourceDesc><p>Produced from a Project Gutenberg HTML source"
        " using gutenberg-text-splitter.</p></sourceDesc>"
        "</fileDesc>"
        "</teiHeader>"
        "<text><body>"
        f'<div type="{div_type}" n="{div_n}">'
    )


TEI_BOTTOM = "</div></body></text></TEI>"

# ---------------------------------------------------------------------------
# Gutenberg catalog search and download
# ---------------------------------------------------------------------------

CATALOG_PATH = "meta/pg_catalog.csv"
CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"


def ensure_catalog():
    """Make sure we have the PG catalog CSV. Download if missing or stale."""
    from datetime import datetime, timedelta

    if not os.path.exists(CATALOG_PATH):
        console.print("[yellow]Downloading Project Gutenberg catalog...[/yellow]")
        _download_catalog()
    else:
        a_week_ago = datetime.now() - timedelta(days=7)
        filetime = datetime.fromtimestamp(os.path.getmtime(CATALOG_PATH))
        if filetime < a_week_ago:
            console.print("[yellow]Catalog is over a week old. Updating...[/yellow]")
            _download_catalog()


def _download_catalog():
    """Download the PG catalog CSV."""
    import requests
    try:
        r = requests.get(CATALOG_URL, allow_redirects=False, timeout=30)
        if r.status_code == 200:
            os.makedirs("meta", exist_ok=True)
            with open(CATALOG_PATH, "wb") as f:
                f.write(r.content)
            console.print("[green]Catalog downloaded.[/green]")
        else:
            console.print(f"[red]Error downloading catalog: HTTP {r.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Error downloading catalog: {e}[/red]")


def load_catalog():
    """Load the PG catalog into a DataFrame."""
    import pandas as pd
    return pd.read_csv(
        CATALOG_PATH, sep=",", engine="c", low_memory=False, na_filter=False,
        dtype={"Text#": "uint32", "Title": "object", "Authors": "object", "Subjects": "object"},
    )


def search_catalog(author=None, title=None, subject=None, book_id=None):
    """
    Search the PG catalog. Returns matching rows as a DataFrame.
    Filters can be combined (AND logic).
    """
    ensure_catalog()
    df = load_catalog()

    # Only look at actual texts
    mask = df["Type"] == "Text"

    if author:
        mask = mask & df["Authors"].str.contains(author, na=False, case=False)
    if title:
        mask = mask & df["Title"].str.contains(title, na=False, case=False)
    if subject:
        mask = mask & df["Subjects"].str.contains(subject, na=False, case=False)
    if book_id:
        mask = mask & (df["Text#"] == int(book_id))

    return df[mask]


def display_search_results(results):
    """Print search results as a rich table."""
    if len(results) == 0:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f"Search Results ({len(results)} found)", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Author", style="magenta", max_width=30)
    table.add_column("Title", style="green", max_width=50)
    table.add_column("Language", style="blue", max_width=5)

    for _, row in results.head(30).iterrows():
        table.add_row(str(row["Text#"]), row["Authors"], row["Title"], row.get("Language", ""))

    console.print(table)
    if len(results) > 30:
        console.print(f"[dim]({len(results) - 30} more results not shown. Narrow your search.)[/dim]")


def download_gutenberg(book_id, filename=None):
    """
    Download a Gutenberg HTML text by ID into input/.

    Tries URL formats in order, normalizes encoding to UTF-8.
    Returns the path to the downloaded file, or None on failure.
    """
    import requests

    if filename is None:
        filename = f"pg{book_id}"
    # Strip .html if provided
    filename = filename.replace(".html", "")

    out_path = f"input/{filename}.html"
    if os.path.exists(out_path):
        console.print(f"  [dim]Already exists:[/dim] {out_path}")
        return out_path

    urls = [
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}-images.html.utf8",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-h/{book_id}-h.htm",
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.html.utf8",
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}-images.html",
    ]

    os.makedirs("input", exist_ok=True)

    for url in urls:
        console.print(f"  Trying {url}...")
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                # Normalize to UTF-8: try decoding as UTF-8 first, fall back
                # to Latin-1 (common for legacy Gutenberg .htm files)
                try:
                    text = r.content.decode("utf-8")
                except UnicodeDecodeError:
                    text = r.content.decode("latin-1")
                    console.print(f"  [yellow]Re-encoded from Latin-1 to UTF-8[/yellow]")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                console.print(f"  [green]Downloaded:[/green] {out_path} ({len(r.content) // 1024} KB)")
                return out_path
        except Exception as e:
            console.print(f"  [dim]Failed: {e}[/dim]")

    console.print(f"  [red]Could not download PG #{book_id} -- no HTML version found.[/red]")
    return None

# ---------------------------------------------------------------------------
# Core splitting logic (extracted from splitter.py's process_html)
# ---------------------------------------------------------------------------

def write_section(path, content, tei_head=None):
    """Write a single section file, optionally wrapping in TEI."""
    with open(path, "w", encoding="utf-8") as f:
        if tei_head is not None:
            f.write(tei_head)
        f.write(content)
        if tei_head is not None:
            f.write(TEI_BOTTOM)


def is_end_of_text(text, end_marker):
    """Check whether we've hit the end-of-text marker."""
    if end_marker == "":
        return False
    return end_marker in text


def _filter_to_leaves(elements, element, attrib):
    """Filter matched elements to leaf nodes only.

    When the same selector matches at multiple nesting levels (e.g.
    div.chapter wrapping both BOOK-level and CHAPTER-level containers),
    parent elements contain their children's text, producing stub files
    with duplicate or near-empty content.

    This function removes any matched element that contains other matched
    elements as descendants, keeping only the deepest (leaf) matches.

    Returns (leaves, parents_removed) so the caller can log the filtering.
    """
    element_set = set(id(e) for e in elements)

    leaves = []
    parents_removed = []
    for e in elements:
        # Check if this element contains any OTHER matched element as a descendant
        if attrib:
            nested = e.find_all(element, attrib)
        else:
            nested = e.find_all(element)
        # find_all on a tag searches descendants (not self), so any hit means
        # this element is a parent wrapping other matches
        has_nested_match = any(id(n) in element_set for n in nested)
        if has_nested_match:
            parents_removed.append(e)
        else:
            leaves.append(e)

    return leaves, parents_removed


def _quarantine_small_sections(out_path, section_manifest, warn_words):
    """Move undersized sections to _flagged/ subdirectory for scholarly review.

    Instead of silently dropping or auto-merging small sections (which would
    make implicit theoretical decisions about textual units), this function
    quarantines them so the researcher can decide per-file:
      - paratext (volume title pages, epigraphs) -> delete
      - structural markers (book dividers) -> delete
      - alternating headings (CHAP. I. / TITLE) -> merge manually
      - legitimately short content -> move back to main directory

    Also writes a _manifest.tsv with word counts, status, and content
    previews for all sections.

    Returns (kept, flagged) counts.
    """
    flagged_dir = os.path.join(out_path, "_flagged")
    kept = 0
    flagged = 0
    manifest_entries = []

    for filename, wc in section_manifest:
        filepath = os.path.join(out_path, filename)
        if wc < warn_words and os.path.isfile(filepath):
            # Read content preview (strip TEI markup for readability)
            preview = _read_content_preview(filepath, 120)

            os.makedirs(flagged_dir, exist_ok=True)
            shutil.move(filepath, os.path.join(flagged_dir, filename))
            flagged += 1
            manifest_entries.append((filename, wc, "FLAGGED", preview))
        else:
            kept += 1
            manifest_entries.append((filename, wc, "ok", ""))

    # Write manifest
    manifest_path = os.path.join(out_path, "_manifest.tsv")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("filename\twords\tstatus\tpreview\n")
        for filename, wc, status, preview in manifest_entries:
            safe_preview = preview.replace("\t", " ").replace("\n", " ")
            f.write(f"{filename}\t{wc}\t{status}\t{safe_preview}\n")

    return kept, flagged


def _read_content_preview(filepath, max_chars=120):
    """Read a content preview from a TEI or plain text file.

    For TEI files, extracts just the div content (skipping headers).
    Returns a cleaned single-line string.
    """
    try:
        raw = open(filepath, "r", encoding="utf-8").read()
        # Try to extract div content from TEI
        match = re.search(r'<div[^>]*>(.+?)</div>', raw, re.DOTALL)
        if match:
            preview = match.group(1).strip()[:max_chars]
        else:
            preview = raw[:max_chars]
        return " ".join(preview.split())
    except Exception:
        return "(could not read)"


def process_file(cfg):
    """
    Process a single HTML file into chapter/section files.

    cfg is a dict with keys:
        file            (str)  - path to HTML file
        elem            (str)  - HTML element for chapter boundaries
        attr            (str)  - attribute value to filter elements (optional)
        offset          (int)  - number of leading elements to skip
        year            (str)  - publication year
        output_format   (str)  - "tei" or "plain"
        prefix          (str)  - filename prefix for output files
        title           (str)  - TEI title
        author          (str)  - TEI author
        publisher       (str)  - TEI publisher
        location        (str)  - TEI publication location
        div_type        (str)  - TEI div type (chapter, note, poem, letter, etc.)
        end_marker      (str)  - text that signals end of content
        output_dir      (str)  - base output directory (default: "output")
        excluded_attrs  (list) - attributes to exclude (negative matching)
        boundary_mode   (str)  - "auto", "container", or "sibling"
        warn_words      (int)  - threshold for warning about small sections
    """
    the_file = cfg["file"]
    element = cfg["elem"]
    attrib = cfg.get("attr", "")
    start_pos = cfg.get("offset", 1)
    year = str(cfg.get("year", ""))
    output_format = cfg.get("output_format", "plain")
    prefix = cfg.get("prefix", "")
    title = cfg.get("title", "")
    author = cfg.get("author", "")
    publisher = cfg.get("publisher", "")
    location = cfg.get("location", "")
    div_type = cfg.get("div_type", "chapter")
    end_marker = cfg.get("end_marker", "PROJECT GUTENBERG EBOOK")
    base_output = cfg.get("output_dir", "output")
    excluded_attrs = cfg.get("excluded_attrs", [])
    boundary_mode = cfg.get("boundary_mode", "auto")
    limit = cfg.get("limit", 0)  # 0 = no limit
    warn_words = cfg.get("warn_words", DEFAULT_WARN_WORDS)

    is_tei = output_format == "tei"

    if not os.path.isfile(the_file):
        console.print(f"[red]Error:[/red] File not found: {the_file}")
        return False

    # Build output directory name
    file_stem = os.path.splitext(os.path.basename(the_file))[0]
    if prefix:
        dir_name = prefix
    elif year:
        dir_name = f"{year}-{file_stem}"
    else:
        dir_name = file_stem
    out_path = os.path.join(base_output, dir_name)
    os.makedirs(out_path, exist_ok=True)

    # Read and parse
    contents = read_file(the_file)
    soup = BeautifulSoup(contents, "html.parser")

    # Find elements
    if attrib:
        elements = soup.find_all(element, attrib)
    else:
        elements = soup.find_all(element)

    # --- Leaf-node filtering ---
    # When the same selector matches at multiple nesting levels (e.g.
    # div.chapter for both BOOK and CHAPTER containers), parent elements
    # produce stub files with duplicate content. Filter to leaves only.
    elements, parents_removed = _filter_to_leaves(elements, element, attrib)
    if parents_removed:
        console.print(
            f"  [cyan]Nesting detected:[/cyan] {len(parents_removed)} parent element(s) "
            f"contained other matches and were skipped (keeping {len(elements)} leaves):"
        )
        for p in parents_removed[:10]:
            heading = p.get_text()[:60].strip().replace("\n", " ")
            console.print(f"    [dim]skipped parent:[/dim] {heading}")
        if len(parents_removed) > 10:
            console.print(f"    [dim]...and {len(parents_removed) - 10} more[/dim]")

    container_elems = ["div"]

    # Determine processing mode: container (content inside element) vs
    # sibling (content between boundary markers).
    #   --boundary-mode=auto      (default) auto-detect based on content length
    #   --boundary-mode=container  force container mode (div wraps full chapter)
    #   --boundary-mode=sibling    force sibling mode (div is thin heading wrapper)
    if boundary_mode == "container":
        use_container = True
    elif boundary_mode == "sibling":
        use_container = False
    else:
        # Auto-detect: if the element is a div, sample a few to see if they
        # contain substantial text or are just heading wrappers.
        use_container = element in container_elems
        if use_container and elements:
            sample = elements[start_pos - 1 : start_pos + 2] if len(elements) >= start_pos else elements[:3]
            avg_len = sum(len(e.get_text(strip=True)) for e in sample) / max(len(sample), 1)
            if avg_len < 100:
                use_container = False

    # section_manifest: list of (filename, word_count) for every section written
    if use_container:
        section_manifest = _process_container(
            elements, element, attrib, start_pos, out_path, prefix,
            is_tei, title, author, publisher, location, year,
            div_type, end_marker, excluded_attrs, limit,
        )
    else:
        section_manifest = _process_non_container(
            elements, element, attrib, start_pos, out_path, prefix,
            is_tei, title, author, publisher, location, year,
            div_type, end_marker, limit,
        )

    section_count = len(section_manifest)
    total_words = sum(wc for _, wc in section_manifest)

    file_type_label = "TEI" if is_tei else "plain text"
    console.print(
        f"  [green]Done:[/green] {the_file} -> {out_path}/ "
        f"({section_count} {div_type}s, {total_words:,} words, {file_type_label})"
    )

    # Quarantine undersized sections for scholarly review
    if warn_words > 0 and section_manifest:
        small = [(name, wc) for name, wc in section_manifest if wc < warn_words]
        if small:
            kept, flagged_count = _quarantine_small_sections(
                out_path, section_manifest, warn_words
            )
            console.print(
                f"  [yellow]FLAGGED: {flagged_count}/{section_count} sections "
                f"below {warn_words} words moved to _flagged/ for review:[/yellow]"
            )
            # Show each flagged file with content preview
            for name, wc in small:
                flagged_path = os.path.join(out_path, "_flagged", name)
                preview = ""
                if os.path.isfile(flagged_path):
                    preview = _read_content_preview(flagged_path, 80)
                console.print(
                    f"    [yellow]{name}[/yellow] ({wc} words)"
                    + (f'  [dim]"{preview}"[/dim]' if preview else "")
                )

            console.print(
                f"  [cyan]Review:[/cyan] {out_path}/_manifest.tsv"
            )
            console.print(
                f"  [cyan]To restore:[/cyan] mv {out_path}/_flagged/FILENAME {out_path}/"
            )

            # Extra alarm: if majority of sections are tiny, it's almost
            # certainly a splitting bug, not just a few short poems
            pct = len(small) / len(section_manifest) * 100
            if pct > 50:
                console.print(
                    f"  [bold red]ALERT: {pct:.0f}% of sections are undersized. "
                    f"The split element is probably wrong for this file. "
                    f"Try: poetry run python3 batch-splitter.py --analyze {the_file}[/bold red]"
                )
        else:
            # No small sections -- still write manifest for completeness
            manifest_path = os.path.join(out_path, "_manifest.tsv")
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write("filename\twords\tstatus\tpreview\n")
                for filename, wc in section_manifest:
                    f.write(f"{filename}\t{wc}\tok\t\n")

    return True


def _process_non_container(
    elements, element, attrib, start_pos, out_path, prefix,
    is_tei, title, author, publisher, location, year,
    div_type, end_marker, limit=0,
):
    """Process files where chapters are delimited by boundary elements (h2, h3, hr, etc.).

    Walks the DOM in document order, attributing each text node to the most
    recent boundary element seen. This works whether the boundary elements are
    all top-level siblings or nested at varying depths within wrapper containers.
    Returns a manifest: list of (filename, word_count) tuples.
    """
    manifest = []
    elements_list = list(elements)
    if not elements_list:
        return manifest

    elem_id_set = {id(e) for e in elements_list}

    # Find a common ancestor that contains all boundary elements.
    def _is_descendant(node, ancestor):
        p = node.parent
        while p is not None:
            if p is ancestor:
                return True
            p = p.parent
        return False

    root = elements_list[0].parent
    while root is not None:
        if all(_is_descendant(e, root) or e is root for e in elements_list):
            break
        root = root.parent
    if root is None:
        root = elements_list[0].parent

    # Walk document-order descendants, accumulating text per chapter.
    chapter_text = ['' for _ in elements_list]
    chapter_idx = -1
    end_hit = False
    last_end_chapter = -1

    for node in root.descendants:
        if isinstance(node, Tag):
            if id(node) in elem_id_set:
                chapter_idx = elements_list.index(node)
                chapter_text[chapter_idx] += node.get_text()
            # Other tags: their text is captured via NavigableString descendants.
            continue
        if isinstance(node, NavigableString):
            if chapter_idx < 0:
                continue
            # Skip text inside any boundary element (already captured via get_text).
            in_boundary = False
            p = node.parent
            while p is not None and p is not root:
                if id(p) in elem_id_set:
                    in_boundary = True
                    break
                p = p.parent
            if in_boundary:
                continue
            if end_marker and is_end_of_text(str(node), end_marker):
                end_hit = True
                last_end_chapter = chapter_idx
                break
            chapter_text[chapter_idx] += str(node)

    # Emit chapters subject to start_pos, limit, and end_marker truncation.
    # Matches original semantics: chapter_count restarts at 1 from start_pos.
    chapter_count = 1
    written = 0
    for idx, content in enumerate(chapter_text):
        if (idx + 1) < start_pos:
            continue
        if end_hit and idx > last_end_chapter:
            break
        result = _write_chapter(
            out_path, prefix, is_tei, div_type, chapter_count,
            content, title, author, publisher, location, year,
        )
        manifest.append(result)
        chapter_count += 1
        written += 1
        if limit and written >= limit:
            break

    return manifest


def _process_container(
    elements, element, attrib, start_pos, out_path, prefix,
    is_tei, title, author, publisher, location, year,
    div_type, end_marker, excluded_attrs, limit=0,
):
    """Process files where chapters are wrapped in container elements (div, etc.).
    Returns a manifest: list of (filename, word_count) tuples."""
    i = 2 - start_pos
    manifest = []

    for elem in list(elements):
        # Check for end of text
        try:
            elem_text = elem.get_text()
        except AttributeError:
            elem_text = str(elem)

        if end_marker and is_end_of_text(elem_text, end_marker):
            break

        # Each matched container element IS a chapter/section.
        if i >= 1:
            result = _write_chapter(
                out_path, prefix, is_tei, div_type, i,
                elem_text, title, author, publisher, location, year,
            )
            manifest.append(result)
            if limit and len(manifest) >= limit:
                break

        i += 1

    return manifest


def _write_chapter(
    out_path, prefix, is_tei, div_type, n,
    content, title, author, publisher, location, year,
):
    """Write a single chapter/section file.

    If prefix is set, filenames are: {prefix}-{div_type}_{n}
    Otherwise, TEI files are: tei_{div_type}_{n}
    and plain files are: {div_type}_{n}

    Returns (filename, word_count) tuple.
    """
    if prefix:
        filename = f"{prefix}-{div_type}_{n}"
    elif is_tei:
        filename = f"tei_{div_type}_{n}"
    else:
        filename = f"{div_type}_{n}"

    word_count = len(content.split())

    if is_tei:
        tei_head = make_tei_head(title, author, publisher, location, year, div_type, n)
        write_section(os.path.join(out_path, filename), content, tei_head)
    else:
        write_section(os.path.join(out_path, filename), content)

    return (filename, word_count)


# ---------------------------------------------------------------------------
# Corpus config loading
# ---------------------------------------------------------------------------

def load_corpus_config(config_path):
    """Load a YAML corpus config and return a list of per-file config dicts."""
    try:
        import yaml
    except ImportError:
        console.print("[red]Error:[/red] PyYAML is required for --config mode. Install it with: pip install pyyaml")
        sys.exit(1)

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    corpus_name = raw.get("corpus_name", "corpus")
    default_format = raw.get("output_format", "plain")
    default_output = raw.get("output_dir", "output")
    default_warn_words = raw.get("warn_words", DEFAULT_WARN_WORDS)
    texts = raw.get("texts", [])

    configs = []
    for entry in texts:
        tei_block = entry.get("tei", {})

        # If gutenberg_id is specified, download the file first
        file_path = entry.get("file", "")
        gutenberg_id = entry.get("gutenberg_id", None)
        if gutenberg_id and not file_path:
            # Auto-generate filename from ID
            file_path = f"input/pg{gutenberg_id}.html"
        elif gutenberg_id and file_path:
            # Use the specified filename but download by ID
            pass

        cfg = {
            "file": file_path,
            "gutenberg_id": gutenberg_id,
            "elem": entry["elem"],
            "attr": entry.get("attr", ""),
            "offset": entry.get("offset", 1),
            "year": entry.get("year", ""),
            "output_format": entry.get("output_format", default_format),
            "prefix": entry.get("prefix", ""),
            "title": tei_block.get("title", ""),
            "author": tei_block.get("author", ""),
            "publisher": tei_block.get("publisher", ""),
            "location": tei_block.get("location", ""),
            "div_type": tei_block.get("div_type", entry.get("div_type", "chapter")),
            "end_marker": entry.get("end_marker", "PROJECT GUTENBERG EBOOK"),
            "output_dir": entry.get("output_dir", default_output),
            "excluded_attrs": entry.get("excluded_attrs", []),
            "boundary_mode": entry.get("boundary_mode", "auto"),
            "limit": entry.get("limit", 0),
            "warn_words": entry.get("warn_words", default_warn_words),
        }
        configs.append(cfg)

    return corpus_name, configs


# ---------------------------------------------------------------------------
# Analyze mode
# ---------------------------------------------------------------------------

def analyze_file(filepath):
    """Scan an HTML file and suggest splitting options."""
    if not os.path.isfile(filepath):
        console.print(f"[red]Error:[/red] File not found: {filepath}")
        return

    soup = BeautifulSoup(read_file(filepath), "html.parser")

    basename = os.path.basename(filepath)
    console.print(f"\n[bold]Analyzing:[/bold] {basename}\n")

    # Count all elements
    all_tags = {}
    for tag in soup.find_all(True):
        all_tags[tag.name] = all_tags.get(tag.name, 0) + 1

    # Show element counts
    elem_table = Table(title="Element counts", show_lines=False)
    elem_table.add_column("Count", justify="right")
    elem_table.add_column("Element")
    for tag, count in sorted(all_tags.items(), key=lambda x: -x[1])[:15]:
        elem_table.add_row(str(count), tag)
    console.print(elem_table)

    # Find chapter-like patterns
    suggestions = []

    # Check divs with class attributes
    divs = soup.find_all("div")
    div_classes = {}
    for d in divs:
        for cls in d.get("class", []):
            div_classes[cls] = div_classes.get(cls, 0) + 1

    def is_structural_class(cls):
        """Heuristic: structural classes use readable words like 'chapter',
        while Gutenberg formatting classes use short CSS abbreviations
        like 'fsz6', 'dpp01', 'dctr01', 'padtopa', etc."""
        cl = cls.lower()
        # Explicit skip list: non-chapter content and known formatting classes
        skip_classes = {
            # Content types that aren't chapters
            "footnote", "endnote", "footnotes", "endnotes", "note", "notes",
            "toc", "contents", "bibliography", "index", "colophon",
            "poem", "stanza", "verse", "epigraph", "dedication",
            "sidebar", "nav", "navbar", "header", "footer",
            # Common Gutenberg/CSS presentation classes
            "clearfix", "nowrap", "pright", "padtopa", "tafmono",
            "dtablebox", "dpoemctr", "dstanzactr", "dquoteverse",
            "dsdnote", "figcenter", "figright", "figleft",
            "blockquot", "smcap", "dsynopsis", "dblockquote",
            "dkeeptgth", "dcenter", "dletter", "dsalute",
            "dsignature", "daddress",
        }
        if cl in skip_classes:
            return False
        # Likely structural: contains words like chapter, section, part, book
        structural_words = {"chapter", "section", "part", "book", "act",
                           "scene", "canto", "letter", "volume", "div"}
        if cl in structural_words or any(w in cl for w in structural_words):
            return True
        # Likely formatting: very short, has digits, or looks like CSS shorthand
        if len(cl) <= 5:
            return False
        if any(c.isdigit() for c in cl):
            return False
        # Gutenberg uses d-prefixed classes for display formatting
        # (dsdnote, dtablebox, dsynopsis, dblockquote, dkeeptgth, etc.)
        if cl.startswith("d") and cl[1:].isalpha():
            return False
        # Ambiguous: allow if it looks like a real word (all alpha, 6+ chars)
        return cl.isalpha() and len(cl) >= 6

    for cls, count in sorted(div_classes.items(), key=lambda x: -x[1]):
        if count >= 3 and is_structural_class(cls):
            sample_divs = soup.find_all("div", cls)
            avg_len = sum(len(d.get_text(strip=True)) for d in sample_divs[:5]) / min(len(sample_divs), 5)
            mode = "container" if avg_len >= 100 else "sibling"
            suggestions.append({
                "elem": "div", "attr": cls, "count": count,
                "elems": sample_divs,
                "mode": mode, "avg_len": int(avg_len),
            })

    # Check heading elements
    for tag in ["h1", "h2", "h3", "h4"]:
        elems = soup.find_all(tag)
        if 3 <= len(elems) <= 200:
            suggestions.append({
                "elem": tag, "attr": "", "count": len(elems),
                "elems": elems,
                "mode": "sibling", "avg_len": 0,
            })

    # Check hr elements
    hrs = soup.find_all("hr")
    if 3 <= len(hrs) <= 200:
        suggestions.append({
            "elem": "hr", "attr": "", "count": len(hrs),
            "elems": hrs,
            "mode": "sibling", "avg_len": 0,
        })

    # Sort suggestions: prefer semantic elements (div with class, headings)
    # over hr, and prefer chapter-like counts (5-100) over outliers
    def score(s):
        c = s["count"]
        in_range = 1 if 5 <= c <= 100 else 0
        # Prefer divs with class attrs (most semantic), then headings, then hr
        if s["elem"] == "div" and s["attr"]:
            elem_score = 3
        elif s["elem"] in ("h1", "h2", "h3", "h4"):
            elem_score = 2
        elif s["elem"] == "hr":
            elem_score = 0
        else:
            elem_score = 1
        return (in_range, elem_score, c)
    suggestions.sort(key=score, reverse=True)

    if not suggestions:
        console.print("\n[yellow]No obvious chapter patterns found.[/yellow] "
                      "Try the interactive splitter (splitter.py) for manual exploration.")
        return

    # Display suggestions with samples
    console.print()
    # Show top 5 options (more are noise)
    display_limit = min(5, len(suggestions))
    if len(suggestions) > display_limit:
        console.print(f"[dim]Showing top {display_limit} of {len(suggestions)} options[/dim]")
    for i, s in enumerate(suggestions[:display_limit], 1):
        attr_str = f' attr="{s["attr"]}"' if s["attr"] else ""
        mode_note = f" [dim](detected: {s['mode']} mode, avg {s['avg_len']} chars)[/dim]" if s["elem"] == "div" else ""
        console.print(f"[bold cyan]Option {i}:[/bold cyan] elem={s['elem']}{attr_str}  "
                       f"({s['count']} matches){mode_note}")

        elems = s["elems"]

        # Cap hr display at 5 since they carry no text
        if s["elem"] == "hr":
            console.print(f"  [dim]{s['count']} horizontal rules (use as section boundaries)[/dim]")
            console.print()
            continue

        sample_table = Table(show_header=True, show_lines=False, padding=(0, 2))
        sample_table.add_column("Pos", justify="right", style="dim")
        sample_table.add_column("Sample text")
        sample_table.add_column("Size", justify="right")

        for j, elem in enumerate(elems, 1):
            text = elem.get_text()[:60].strip()

            # For container divs, show the content length of the div
            if s["mode"] == "container":
                char_count = len(elem.get_text(strip=True))
            else:
                # For sibling mode (headings, thin divs), show the size
                # of content between this element and the next one
                char_count = 0
                for sib in elem.next_siblings:
                    if sib.name == s["elem"]:
                        break
                    if hasattr(sib, 'get_text'):
                        char_count += len(sib.get_text(strip=True))
                    elif isinstance(sib, str):
                        char_count += len(sib.strip())

            if char_count < 50:
                size_str = f"[yellow]{char_count}[/yellow]"
            elif char_count < 500:
                size_str = f"[dim]{char_count}[/dim]"
            else:
                size_str = str(char_count)

            if not text:
                text = "[dim](empty)[/dim]"
            sample_table.add_row(str(j), text, size_str)

        console.print(sample_table)
        console.print()

    # Suggest the best option: prefer heading/div options with chapter-like
    # counts over hr, and suggest the offset that skips thin leading elements
    best = suggestions[0]
    attr_flag = f' --attr {best["attr"]}' if best["attr"] else ""

    # Auto-detect offset: look for the first element whose heading text
    # matches a chapter/letter pattern. Fall back to first element with
    # >= 1000 chars of content.
    chapter_pattern = re.compile(
        r'^\s*(chapter|chap\.?|letter|book|part|canto|section|act|scene)\s',
        re.IGNORECASE
    )

    offset = 1
    # First pass: look for chapter-like heading text
    for j, elem in enumerate(best["elems"]):
        heading = elem.get_text()[:40].strip()
        if chapter_pattern.match(heading):
            offset = j + 1
            break
    else:
        # Second pass: fall back to first element with substantial content
        for j, elem in enumerate(best["elems"]):
            if best["mode"] == "container":
                char_count = len(elem.get_text(strip=True))
            else:
                char_count = 0
                for sib in elem.next_siblings:
                    if sib.name == best["elem"]:
                        break
                    if hasattr(sib, 'get_text'):
                        char_count += len(sib.get_text(strip=True))
                    elif isinstance(sib, str):
                        char_count += len(sib.strip())
            if char_count >= 1000:
                offset = j + 1
                break

    console.print("[bold]Suggested command:[/bold]")
    console.print(f"  python batch-splitter.py --file {filepath} "
                  f"--elem {best['elem']}{attr_flag} --offset {offset} --tei")
    console.print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Batch-process HTML texts into chapter files (plain text or TEI XML).",
        epilog="See corpus_example.yaml for multi-file corpus configuration.",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--config", metavar="YAML",
        help="Path to a YAML corpus config file for multi-file processing.",
    )
    mode.add_argument(
        "--file", metavar="HTML",
        help="Path to a single HTML file to process.",
    )
    mode.add_argument(
        "--search", action="store_true",
        help="Search the Project Gutenberg catalog.",
    )
    mode.add_argument(
        "--download", metavar="ID", type=int,
        help="Download a Gutenberg text by ID into input/.",
    )
    mode.add_argument(
        "--analyze", metavar="HTML",
        help="Analyze an HTML file and suggest splitting options.",
    )

    # Search options
    search_opts = parser.add_argument_group("search options (used with --search)")
    search_opts.add_argument("--search-author", metavar="NAME",
                             help="Filter by author name.")
    search_opts.add_argument("--search-title", metavar="TITLE",
                             help="Filter by title.")
    search_opts.add_argument("--search-subject", metavar="SUBJECT",
                             help="Filter by subject.")

    # Download options
    dl_opts = parser.add_argument_group("download options (used with --download)")
    dl_opts.add_argument("--save-as", metavar="NAME",
                         help="Filename for downloaded text (without .html).")

    # Single-file options
    single = parser.add_argument_group("single-file options")
    single.add_argument("--elem", help="HTML element for chapter boundaries (e.g. h3, div, hr).")
    single.add_argument("--attr", default="", help="Attribute value to filter elements.")
    single.add_argument("--offset", type=int, default=1, help="Number of leading elements to skip (default: 1).")
    single.add_argument("--year", default="", help="Publication year.")
    single.add_argument("--tei", action="store_true", help="Output TEI XML instead of plain text.")
    single.add_argument("--prefix", default="",
                          help="Filename prefix. If set, files are named {prefix}-chapter_1 etc. "
                               "Example: --prefix '1818-ENG18180--Shelley' produces "
                               "1818-ENG18180--Shelley-chapter_1.")
    single.add_argument("--output-dir", default="output", help="Base output directory (default: output).")

    # TEI metadata
    tei_opts = parser.add_argument_group("TEI metadata (used with --tei)")
    tei_opts.add_argument("--title", default="", help="TEI title.")
    tei_opts.add_argument("--author", default="", help="TEI author.")
    tei_opts.add_argument("--publisher", default="", help="TEI publisher.")
    tei_opts.add_argument("--location", default="", help="TEI publication location.")
    tei_opts.add_argument("--div-type", default="chapter",
                          help="TEI div type: chapter, note, poem, letter, section (default: chapter).")
    tei_opts.add_argument("--end-marker", default="PROJECT GUTENBERG EBOOK",
                          help='End-of-text marker. Use "" for non-Gutenberg sources.')

    # Processing mode
    parser.add_argument("--boundary-mode", default="auto",
                        choices=["auto", "container", "sibling"],
                        help="How to extract chapter text. "
                             "auto: detect automatically (default). "
                             "container: content is inside the matched element. "
                             "sibling: content follows the matched element as siblings.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Maximum number of chapters to output (0 = no limit).")
    parser.add_argument("--warn-words", type=int, default=DEFAULT_WARN_WORDS,
                        help=f"Warn about sections below this word count (default: {DEFAULT_WARN_WORDS}). "
                             "Set to 0 to disable warnings.")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.search:
        # ---- Search mode ----
        if not args.search_author and not args.search_title and not args.search_subject:
            console.print("[red]Error:[/red] --search requires at least one of "
                          "--search-author, --search-title, or --search-subject.")
            sys.exit(1)

        results = search_catalog(
            author=args.search_author,
            title=args.search_title,
            subject=args.search_subject,
        )
        display_search_results(results)

    elif args.download:
        # ---- Download mode ----
        download_gutenberg(args.download, filename=args.save_as)

    elif args.analyze:
        # ---- Analyze mode ----
        analyze_file(args.analyze)

    elif args.config:
        # ---- Corpus mode ----
        if not os.path.isfile(args.config):
            console.print(f"[red]Error:[/red] Config file not found: {args.config}")
            sys.exit(1)

        corpus_name, configs = load_corpus_config(args.config)
        console.print(f"\n[bold]Processing corpus:[/bold] {corpus_name} ({len(configs)} texts)\n")

        # Auto-download any texts with gutenberg_id
        for cfg in configs:
            if cfg.get("gutenberg_id") and not os.path.isfile(cfg["file"]):
                filename = os.path.splitext(os.path.basename(cfg["file"]))[0]
                download_gutenberg(cfg["gutenberg_id"], filename=filename)

        results = Table(title="Corpus Build Results", show_lines=True)
        results.add_column("File", style="cyan")
        results.add_column("Status", justify="center")
        results.add_column("Output", style="magenta")

        success = 0
        for cfg in configs:
            ok = process_file(cfg)
            if ok:
                success += 1
                if cfg.get("prefix"):
                    out = os.path.join(cfg.get("output_dir", "output"), cfg["prefix"])
                else:
                    file_stem = os.path.splitext(os.path.basename(cfg["file"]))[0]
                    year_str = str(cfg.get("year", ""))
                    dir_name = f"{year_str}-{file_stem}" if year_str else file_stem
                    out = os.path.join(cfg.get("output_dir", "output"), dir_name)
                results.add_row(cfg["file"], "[green]OK[/green]", out)
            else:
                results.add_row(cfg["file"], "[red]FAILED[/red]", "")

        console.print()
        console.print(results)
        console.print(f"\n[bold]{success}/{len(configs)}[/bold] texts processed successfully.\n")

    else:
        # ---- Single-file mode ----
        if not args.elem:
            console.print("[red]Error:[/red] --elem is required in single-file mode.")
            sys.exit(1)

        cfg = {
            "file": args.file,
            "elem": args.elem,
            "attr": args.attr,
            "offset": args.offset,
            "year": args.year,
            "output_format": "tei" if args.tei else "plain",
            "prefix": args.prefix,
            "title": args.title,
            "author": args.author,
            "publisher": args.publisher,
            "location": args.location,
            "div_type": args.div_type,
            "end_marker": args.end_marker,
            "output_dir": args.output_dir,
            "excluded_attrs": [],
            "boundary_mode": args.boundary_mode,
            "limit": args.limit,
            "warn_words": args.warn_words,
        }
        process_file(cfg)


if __name__ == "__main__":
    main()
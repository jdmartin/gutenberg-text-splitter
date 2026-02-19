#!/usr/bin/env python

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
import sys

from bs4 import BeautifulSoup
from rich import print
from rich.console import Console
from rich.table import Table

console = Console()

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

    url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}-images.html.utf8"
    console.print(f"  Downloading PG #{book_id} -> {out_path}...")

    try:
        r = requests.get(url, allow_redirects=False, timeout=30)
        if r.status_code == 200:
            os.makedirs("input", exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(r.content)
            console.print(f"  [green]Downloaded:[/green] {out_path} ({len(r.content) // 1024} KB)")
            return out_path
        else:
            console.print(f"  [red]HTTP {r.status_code}[/red] -- no HTML version available for PG #{book_id}")
            return None
    except Exception as e:
        console.print(f"  [red]Download failed:[/red] {e}")
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

    is_tei = output_format == "tei"

    if not os.path.isfile(the_file):
        console.print(f"[red]Error:[/red] File not found: {the_file}")
        return False

    # Build output directory name
    file_stem = os.path.splitext(os.path.basename(the_file))[0]
    if year:
        dir_name = f"{year}-{file_stem}"
    else:
        dir_name = file_stem
    out_path = os.path.join(base_output, dir_name)
    os.makedirs(out_path, exist_ok=True)

    # Read and parse
    with open(the_file, "r", encoding="utf-8") as f:
        contents = f.read()
    soup = BeautifulSoup(contents, "html.parser")

    # Find elements
    if attrib:
        elements = soup.find_all(element, attrib)
    else:
        elements = soup.find_all(element)

    container_elems = ["div"]
    section_count = 0

    if element in container_elems:
        section_count = _process_container(
            elements, element, attrib, start_pos, out_path, prefix,
            is_tei, title, author, publisher, location, year,
            div_type, end_marker, excluded_attrs,
        )
    else:
        section_count = _process_non_container(
            elements, element, attrib, start_pos, out_path, prefix,
            is_tei, title, author, publisher, location, year,
            div_type, end_marker,
        )

    file_type_label = "TEI" if is_tei else "plain text"
    console.print(
        f"  [green]Done:[/green] {the_file} -> {out_path}/ "
        f"({section_count} {div_type}s, {file_type_label})"
    )
    return True


def _process_non_container(
    elements, element, attrib, start_pos, out_path, prefix,
    is_tei, title, author, publisher, location, year,
    div_type, end_marker,
):
    """Process files where chapters are delimited by sibling elements (h2, h3, hr, etc.)."""
    # In Jon's original code:
    #   i tracks position in the element list (1-indexed)
    #   chapter_count tracks the output file number (1-indexed)
    #   start_pos is the position at which we start writing (skip elements before it)
    chapter_content = ""
    i = 1
    chapter_count = 1
    sections_written = 0

    for elem in list(elements):
        chapter_content = elem.get_text()

        for sibling in elem.next_siblings:
            # Check for end of text
            try:
                sibling_text = sibling.text
            except AttributeError:
                sibling_text = str(sibling)

            if end_marker and is_end_of_text(sibling_text, end_marker):
                if i >= start_pos:
                    _write_chapter(
                        out_path, prefix, is_tei, div_type, chapter_count,
                        chapter_content, title, author, publisher, location, year,
                    )
                    sections_written += 1
                    chapter_count += 1
                i += 1
                return sections_written

            # Check if we've hit the next chapter boundary or end of siblings
            try:
                next_elem_name = sibling.next_element.name if sibling.next_element else None
            except AttributeError:
                next_elem_name = None

            if next_elem_name == element or sibling.next_sibling is None:
                if i >= start_pos:
                    _write_chapter(
                        out_path, prefix, is_tei, div_type, chapter_count,
                        chapter_content, title, author, publisher, location, year,
                    )
                    sections_written += 1
                    chapter_count += 1
                i += 1
                chapter_content = ""
                break
            else:
                try:
                    chapter_content += sibling.get_text()
                except AttributeError:
                    chapter_content += str(sibling)

    return sections_written


def _process_container(
    elements, element, attrib, start_pos, out_path, prefix,
    is_tei, title, author, publisher, location, year,
    div_type, end_marker, excluded_attrs,
):
    """Process files where chapters are wrapped in container elements (div, etc.)."""
    # Jon's offset math: if start_pos is 7, then i starts at 2-7 = -5.
    # After 6 increments, i reaches 1 and we start writing.
    i = 2 - start_pos
    sections_written = 0

    for elem in list(elements):
        # Check for end of text
        try:
            elem_text = elem.get_text()
        except AttributeError:
            elem_text = str(elem)

        if end_marker and is_end_of_text(elem_text, end_marker):
            break

        # Each matched container element IS a chapter/section.
        # Grab its full text content.
        if i >= 1:
            _write_chapter(
                out_path, prefix, is_tei, div_type, i,
                elem_text, title, author, publisher, location, year,
            )
            sections_written += 1

        i += 1

    return sections_written


def _write_chapter(
    out_path, prefix, is_tei, div_type, n,
    content, title, author, publisher, location, year,
):
    """Write a single chapter/section file."""
    if is_tei:
        filename = f"{prefix}tei_{div_type}_{n}"
        tei_head = make_tei_head(title, author, publisher, location, year, div_type, n)
        write_section(os.path.join(out_path, filename), content, tei_head)
    else:
        filename = f"{prefix}{div_type}_{n}"
        write_section(os.path.join(out_path, filename), content)


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
        }
        configs.append(cfg)

    return corpus_name, configs


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
    single.add_argument("--prefix", default="", help="Filename prefix for output files.")
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
        }
        process_file(cfg)


if __name__ == "__main__":
    main()
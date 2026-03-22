#!/usr/bin/env python3
"""
Gulf Arabic Anki Deck Generator

Downloads the CAMeL DA (Dialectal Arabic) frequency list, filters for
Gulf Arabic words, and produces a TSV file importable into Anki.

Content enrichment (translations, example sentences, transliteration,
pronunciation notes) is done via the Anthropic Claude API.

Usage:
    # Step 1: Filter Gulf words from DA frequency list
    python generate_gulf_anki.py --filter --target-count 5500

    # Step 2: Enrich with translations via Claude API
    python generate_gulf_anki.py --enrich --batch-size 25

    # Step 3: Merge into final Anki TSV
    python generate_gulf_anki.py --merge --output output/gulf_arabic_anki.tsv

    # Or do everything at once:
    python generate_gulf_anki.py --all --target-count 5500

Requirements:
    pip install requests anthropic
    export ANTHROPIC_API_KEY=sk-...
"""

import argparse
import csv
import io
import json
import logging
import os
import re
import sys
import time
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

# Add parent dir so we can import gulf_markers when run from anki/ dir
sys.path.insert(0, str(Path(__file__).parent))
from gulf_markers import GULF_SEED_WORDS, NON_GULF_DIALECT_WORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# --- Constants ---
DA_URL = (
    "https://github.com/CAMeL-Lab/Camel_Arabic_Frequency_Lists"
    "/releases/download/v1.0/DA_freq_lists.tsv.zip"
)
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
ENRICHED_DIR = OUTPUT_DIR / "enriched"
WORDS_FILE = OUTPUT_DIR / "gulf_words.tsv"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"
DEFAULT_OUTPUT = OUTPUT_DIR / "gulf_arabic_anki.tsv"
DEFAULT_MODEL = "claude-sonnet-4-20250514"


# ============================================================
# PHASE 1: Download and parse the DA frequency list
# ============================================================

def download_da_frequency_list() -> list[tuple[str, int]]:
    """Download and parse the DA frequency list. Returns [(word, freq), ...]."""
    cache_path = OUTPUT_DIR / "DA_freq_lists.tsv.zip"

    if cache_path.exists():
        log.info("Using cached DA frequency list: %s", cache_path)
        data = cache_path.read_bytes()
    else:
        log.info("Downloading DA frequency list from GitHub Releases...")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(DA_URL, timeout=120, stream=True)
        resp.raise_for_status()
        data = resp.content
        cache_path.write_bytes(data)
        log.info("Downloaded %.1f MB", len(data) / 1e6)

    # Extract TSV from ZIP
    log.info("Extracting TSV from ZIP...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        tsv_name = next((n for n in names if n.endswith(".tsv")), names[0])
        tsv_bytes = zf.read(tsv_name)

    # Parse TSV
    log.info("Parsing frequency list...")
    entries = []
    text = tsv_bytes.decode("utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            word = parts[0].strip()
            try:
                freq = int(parts[1].strip())
            except ValueError:
                # Try reversed column order (RTL display issue)
                try:
                    freq = int(parts[0].strip())
                    word = parts[1].strip()
                except ValueError:
                    continue
            # Only keep Arabic script words
            if word and re.search(r"[\u0600-\u06FF]", word):
                entries.append((word, freq))

    # Sort by frequency descending
    entries.sort(key=lambda x: x[1], reverse=True)
    log.info("Parsed %d entries from DA frequency list", len(entries))
    return entries


# ============================================================
# PHASE 2: Filter for Gulf Arabic words
# ============================================================

def filter_gulf_words(
    entries: list[tuple[str, int]], target_count: int = 5500
) -> list[tuple[str, int, str]]:
    """
    Filter DA frequency list for Gulf Arabic words.

    Returns [(word, freq, tier), ...] where tier is 'A', 'B', or 'C'.
    """
    selected = {}  # word -> (freq, tier)
    word_to_freq = {w: f for w, f in entries}
    word_to_rank = {w: i + 1 for i, (w, _) in enumerate(entries)}

    # --- Tier A: Curated Gulf seed words ---
    tier_a_count = 0
    for word in GULF_SEED_WORDS:
        if word in word_to_freq:
            selected[word] = (word_to_freq[word], "A")
            tier_a_count += 1
        else:
            # Include even if not in DA list (with freq 0) — it's a known Gulf word
            selected[word] = (0, "A")
            tier_a_count += 1
    log.info("Tier A: %d Gulf seed words (%d found in DA list)",
             tier_a_count, sum(1 for w in GULF_SEED_WORDS if w in word_to_freq))

    # --- Tier B: High-frequency DA words, excluding non-Gulf ---
    tier_b_count = 0
    scan_limit = min(len(entries), 8000)
    for word, freq in entries[:scan_limit]:
        if word in selected:
            continue
        if word in NON_GULF_DIALECT_WORDS:
            continue
        # Skip very short words (single char) that are likely noise
        if len(word) < 2:
            continue
        selected[word] = (freq, "B")
        tier_b_count += 1
    log.info("Tier B: %d high-frequency words (from top %d)", tier_b_count, scan_limit)

    # --- Tier C: Extended range to hit target ---
    if len(selected) < target_count:
        tier_c_count = 0
        extended_limit = min(len(entries), 25000)
        for word, freq in entries[scan_limit:extended_limit]:
            if len(selected) >= target_count:
                break
            if word in selected:
                continue
            if word in NON_GULF_DIALECT_WORDS:
                continue
            if len(word) < 2:
                continue
            selected[word] = (freq, "C")
            tier_c_count += 1
        log.info("Tier C: %d extended words (ranks %d-%d)",
                 tier_c_count, scan_limit + 1, extended_limit)

    # Build final list sorted by frequency
    result = [(w, f, t) for w, (f, t) in selected.items()]
    result.sort(key=lambda x: x[1], reverse=True)
    log.info("Total selected: %d words (target: %d)", len(result), target_count)
    return result


def save_filtered_words(words: list[tuple[str, int, str]]):
    """Save filtered word list to TSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORDS_FILE, "w", encoding="utf-8") as f:
        f.write("word\tfrequency\ttier\n")
        for word, freq, tier in words:
            f.write(f"{word}\t{freq}\t{tier}\n")
    log.info("Saved %d words to %s", len(words), WORDS_FILE)


def load_filtered_words() -> list[tuple[str, int, str]]:
    """Load previously filtered words."""
    words = []
    with open(WORDS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            words.append((row["word"], int(row["frequency"]), row["tier"]))
    return words


# ============================================================
# PHASE 3: Enrich words with Claude API
# ============================================================

ENRICHMENT_PROMPT = """You are an expert in Gulf Arabic (خليجي) — the Arabic dialects spoken in Saudi Arabia, UAE, Kuwait, Bahrain, Qatar, and Oman.

I will give you a batch of Arabic words. For each word, provide:

1. **english**: Concise English translation (1-4 words)
2. **transliteration**: Romanized pronunciation using this scheme:
   - Use common chat Arabic conventions (e.g., 3=ع, 7=ح, 5=خ, 6=ط, 9=ص, '=ء)
   - Or simplified Latin: sh=ش, th=ث, kh=خ, gh=غ, dh=ذ
   - Gulf ق is usually pronounced as "g" — transliterate accordingly
   - Gulf ك before front vowels sometimes = "ch" (Kuwaiti) — use "k" as default
3. **example_ar**: A natural Gulf Arabic sentence using this word (5-10 words, conversational)
4. **example_en**: English translation of the example sentence
5. **pronunciation**: Brief Gulf-specific pronunciation note (1 sentence). Mention if:
   - ق is pronounced as /g/
   - Any letter has a Gulf-specific realization
   - Stress pattern is notable
   - If nothing special, just say "Standard Gulf pronunciation."

Respond with ONLY a JSON array. Each element must have exactly these keys:
{"word", "english", "transliteration", "example_ar", "example_en", "pronunciation"}

Important:
- Use Gulf Arabic dialect in example sentences (NOT MSA)
- Keep examples practical and conversational
- If a word is pan-Arabic (used everywhere), still give the Gulf-flavored example
- If a word has multiple meanings, give the most common Gulf usage

Here are the words:
{words}
"""


def load_checkpoint() -> dict:
    """Load enrichment checkpoint."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed_batches": [], "enriched_words": {}}


def save_checkpoint(checkpoint: dict):
    """Save enrichment checkpoint."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def enrich_batch(words: list[str], model: str = DEFAULT_MODEL) -> list[dict]:
    """Send a batch of words to Claude API for enrichment."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: 'anthropic' package required for enrichment.")
        print("Install with: pip install anthropic")
        print("Set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    client = anthropic.Anthropic()
    words_text = "\n".join(f"- {w}" for w in words)
    prompt = ENRICHMENT_PROMPT.format(words=words_text)

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse JSON from response
    response_text = message.content[0].text.strip()
    # Try to extract JSON array from response
    json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    else:
        log.warning("Could not parse JSON from response, trying full text...")
        return json.loads(response_text)


def run_enrichment(batch_size: int = 25, model: str = DEFAULT_MODEL):
    """Enrich all filtered words using Claude API."""
    words_data = load_filtered_words()
    checkpoint = load_checkpoint()
    enriched = checkpoint.get("enriched_words", {})
    completed = set(checkpoint.get("completed_batches", []))

    # Words that still need enrichment
    to_enrich = [w for w, _, _ in words_data if w not in enriched]
    log.info("%d words need enrichment (%d already done)", len(to_enrich), len(enriched))

    # Process in batches
    batches = [to_enrich[i:i + batch_size] for i in range(0, len(to_enrich), batch_size)]
    total_batches = len(batches)

    for i, batch in enumerate(batches):
        batch_id = f"batch_{i}"
        if batch_id in completed:
            continue

        log.info("Processing batch %d/%d (%d words)...", i + 1, total_batches, len(batch))

        try:
            results = enrich_batch(batch, model=model)
            for item in results:
                word = item.get("word", "")
                if word:
                    enriched[word] = item
            completed.add(batch_id)

            # Save checkpoint after each batch
            checkpoint["enriched_words"] = enriched
            checkpoint["completed_batches"] = list(completed)
            save_checkpoint(checkpoint)
            log.info("  -> Got %d results, total enriched: %d", len(results), len(enriched))

        except Exception as e:
            log.error("  -> Batch %d failed: %s", i + 1, e)
            log.info("  -> Saving checkpoint and continuing...")
            save_checkpoint(checkpoint)
            # Brief pause before continuing
            time.sleep(2)
            continue

        # Rate limiting pause between batches
        if i < total_batches - 1:
            time.sleep(1)

    # Save enriched data as JSON file too
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    enriched_file = ENRICHED_DIR / "all_enriched.json"
    with open(enriched_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    log.info("Enrichment complete. %d words enriched. Saved to %s", len(enriched), enriched_file)


# ============================================================
# PHASE 4: Merge into Anki TSV
# ============================================================

def merge_to_anki_tsv(output_path: str = None):
    """Merge filtered words + enriched data into Anki-importable TSV."""
    if output_path is None:
        output_path = str(DEFAULT_OUTPUT)

    words_data = load_filtered_words()
    checkpoint = load_checkpoint()
    enriched = checkpoint.get("enriched_words", {})

    if not enriched:
        # Try loading from enriched JSON file
        enriched_file = ENRICHED_DIR / "all_enriched.json"
        if enriched_file.exists():
            with open(enriched_file, "r", encoding="utf-8") as f:
                enriched = json.load(f)

    log.info("Merging %d words with %d enriched entries...", len(words_data), len(enriched))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Anki TSV: tab-separated, UTF-8 with BOM
    # Columns: arabic_word, english, transliteration, example_ar, example_en, pronunciation, rank, tags
    cards_written = 0
    cards_unenriched = 0

    with open(output_path, "w", encoding="utf-8-sig") as f:
        # Write header as comment (Anki ignores lines starting with #)
        f.write("# Gulf Arabic Anki Flashcard Deck\n")
        f.write("# Generated from CAMeL DA Frequency List\n")
        f.write("# Columns: arabic_word | english | transliteration | "
                "example_ar | example_en | pronunciation | rank | tags\n")
        f.write("# Import into Anki: File > Import, select Tab separator\n")
        f.write("#\n")

        for rank, (word, freq, tier) in enumerate(words_data, 1):
            info = enriched.get(word, {})
            english = info.get("english", "")
            translit = info.get("transliteration", "")
            example_ar = info.get("example_ar", "")
            example_en = info.get("example_en", "")
            pronunciation = info.get("pronunciation", "")
            tags = f"gulf_arabic tier_{tier.lower()}"

            if not english:
                cards_unenriched += 1

            # Escape any tabs in fields
            fields = [
                word,
                english,
                translit,
                example_ar,
                example_en,
                pronunciation,
                str(rank),
                tags,
            ]
            fields = [f.replace("\t", " ").replace("\n", "<br>") for f in fields]
            f.write("\t".join(fields) + "\n")
            cards_written += 1

    log.info("Wrote %d cards to %s", cards_written, output_path)
    if cards_unenriched:
        log.warning("%d cards have no enrichment data (translation/examples missing)", cards_unenriched)
    log.info("Import into Anki: File > Import > select the TSV file > set separator to Tab")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gulf Arabic Anki Deck Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Filter Gulf words from DA frequency list
  python generate_gulf_anki.py --filter

  # Enrich with translations via Claude API
  python generate_gulf_anki.py --enrich

  # Merge into Anki TSV
  python generate_gulf_anki.py --merge

  # Do everything at once
  python generate_gulf_anki.py --all

  # Filter only (no API needed)
  python generate_gulf_anki.py --filter-only --target-count 5500
        """,
    )
    parser.add_argument("--filter", action="store_true",
                        help="Run Phase 1+2: Download DA list and filter Gulf words")
    parser.add_argument("--enrich", action="store_true",
                        help="Run Phase 3: Enrich words via Claude API (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--merge", action="store_true",
                        help="Run Phase 4: Merge into Anki TSV")
    parser.add_argument("--all", action="store_true",
                        help="Run all phases (filter + enrich + merge)")
    parser.add_argument("--filter-only", action="store_true",
                        help="Only filter words (no enrichment, produces word list TSV)")
    parser.add_argument("--target-count", type=int, default=5500,
                        help="Target number of words (default: 5500)")
    parser.add_argument("--batch-size", type=int, default=25,
                        help="Words per API batch (default: 25)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"Claude model for enrichment (default: {DEFAULT_MODEL})")
    parser.add_argument("--output", type=str, default=None,
                        help="Output TSV path (default: output/gulf_arabic_anki.tsv)")

    args = parser.parse_args()

    # If no action specified, show help
    if not any([args.filter, args.enrich, args.merge, args.all, args.filter_only]):
        parser.print_help()
        return

    if args.all:
        args.filter = True
        args.enrich = True
        args.merge = True

    if args.filter or args.filter_only:
        log.info("=== Phase 1: Downloading DA frequency list ===")
        entries = download_da_frequency_list()
        log.info("=== Phase 2: Filtering Gulf Arabic words ===")
        words = filter_gulf_words(entries, target_count=args.target_count)
        save_filtered_words(words)

        if args.filter_only:
            log.info("Filter-only mode. Word list saved to %s", WORDS_FILE)
            log.info("To enrich, run: python generate_gulf_anki.py --enrich")
            return

    if args.enrich:
        if not WORDS_FILE.exists():
            log.error("No filtered words found. Run --filter first.")
            sys.exit(1)
        log.info("=== Phase 3: Enriching words via Claude API ===")
        run_enrichment(batch_size=args.batch_size, model=args.model)

    if args.merge:
        if not WORDS_FILE.exists():
            log.error("No filtered words found. Run --filter first.")
            sys.exit(1)
        log.info("=== Phase 4: Merging into Anki TSV ===")
        merge_to_anki_tsv(output_path=args.output)


if __name__ == "__main__":
    main()

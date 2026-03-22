# Gulf Arabic Anki Flashcard Deck Generator

Generate a 5000+ word Anki flashcard deck of Gulf Arabic (خليجي) vocabulary, derived from the [CAMeL Arabic Frequency Lists](https://github.com/CAMeL-Lab/Camel_Arabic_Frequency_Lists) dataset.

Each flashcard includes:
- **Arabic word** (card front)
- **English translation**
- **Transliteration** (romanized pronunciation)
- **Example sentence** in Gulf Arabic dialect
- **Example sentence translation**
- **Pronunciation notes** (Gulf-specific features like ق→g)

## Quick Start

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/Abdalestar/Camel.git
cd Camel

# Install Python dependencies
pip install -r anki/requirements.txt
```

### 2. Filter Gulf Words (No API key needed)

This downloads the DA frequency list and filters for Gulf Arabic words:

```bash
python anki/generate_gulf_anki.py --filter-only --target-count 5500
```

Output: `anki/output/gulf_words.tsv` — a list of 5500 Gulf Arabic words with frequencies.

### 3. Enrich with Translations (Requires API key)

Get an API key from [console.anthropic.com](https://console.anthropic.com):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python anki/generate_gulf_anki.py --enrich
```

This sends words to Claude in batches of 25, generating translations, example sentences, transliteration, and pronunciation notes. Progress is checkpointed — if interrupted, just re-run to resume.

### 4. Generate Anki TSV

```bash
python anki/generate_gulf_anki.py --merge
```

Output: `anki/output/gulf_arabic_anki.tsv`

### 5. Import into Anki

1. Open Anki
2. Go to **File → Import**
3. Select `gulf_arabic_anki.tsv`
4. Set **Field separator** to `Tab`
5. Map the 8 columns:
   | Field # | Maps to |
   |---------|---------|
   | 1 | Front (Arabic Word) |
   | 2 | English Translation |
   | 3 | Transliteration |
   | 4 | Example (Arabic) |
   | 5 | Example (English) |
   | 6 | Pronunciation Notes |
   | 7 | Frequency Rank |
   | 8 | Tags |
6. Click **Import**

### All-in-One Command

Run everything with a single command:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python anki/generate_gulf_anki.py --all --target-count 5500
```

## How It Works

### Word Selection (3-Tier Strategy)

The DA frequency list contains 6.7 million words from ALL Arabic dialects (Egyptian, Levantine, Gulf, Maghrebi, etc.) with no dialect tags. We filter using:

- **Tier A (~400 words)**: Curated Gulf-specific vocabulary (وايد، شلون، خوش، يسولف, etc.)
- **Tier B (~5000 words)**: Top 8000 most frequent DA words, excluding known Egyptian/Levantine/Maghrebi markers
- **Tier C (remaining)**: Extended frequency range to hit the target count

### Content Enrichment

Each word is sent to Claude API in batches, which generates:
- English translation (most common Gulf usage)
- Transliteration using chat Arabic conventions (3=ع, 7=ح, etc.)
- Natural Gulf Arabic example sentence
- English translation of the example
- Gulf-specific pronunciation notes

### Checkpoint/Resume

Enrichment progress is saved to `anki/output/checkpoint.json`. If the process is interrupted (network error, rate limit, etc.), simply re-run `--enrich` and it resumes from where it left off.

## Using with Claude Code CLI (No API Key)

If you have Claude Code Max subscription and prefer not to use the API:

```bash
# Step 1: Filter words (no API needed)
python anki/generate_gulf_anki.py --filter-only

# Step 2: Open the word list in Claude Code and ask it to generate
#          enriched JSON files in anki/output/enriched/
# Example prompt: "Read anki/output/gulf_words.tsv and generate
#   enrichment data for the first 100 words as JSON"

# Step 3: Merge when enrichment is done
python anki/generate_gulf_anki.py --merge
```

## Requirements

- Python 3.8+
- `requests` — for downloading the frequency list
- `anthropic` — for content enrichment via Claude API (optional if using Claude Code CLI)

## Citation

This tool uses data from the CAMeL Arabic Frequency Lists, derived from:

```
@inproceedings{inoue-etal-2021-interplay,
    title = "The Interplay of Variant, Size, and Task Type in {A}rabic Pre-trained Language Models",
    author = "Inoue, Go and Alhafni, Bashar and Baimukan, Guilnara and Bouamor, Houda and Habash, Nizar",
    booktitle = "Proceedings of the Sixth Arabic Natural Language Processing Workshop",
    year = "2021",
    url = "https://aclanthology.org/2021.wanlp-1.10",
}
```

Data is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

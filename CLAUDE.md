# CLAUDE.md

## Project Overview

**CAMeL Arabic Frequency Lists** is a dataset distribution repository maintained by the CAMeL Lab. It provides Arabic word frequency lists derived from the pretraining datasets used for the [CAMeLBERT](https://huggingface.co/collections/CAMeL-Lab/camelbert-653f42bfcbc8ae32a51a692d) family of models.

This is **not a software project** — it contains no source code, no build system, and no tests. It serves as a metadata and documentation hub for downloadable dataset files hosted via GitHub Releases.

## Repository Structure

```
├── README.md        # Main documentation: dataset description, download links, examples, citation
├── LICENSE.txt      # CC BY-SA 4.0 license with citation requirements
└── CITATION.cff     # Machine-readable citation metadata (Citation File Format v1.0.0)
```

There are no other directories or files. The actual frequency data (TSV files) is distributed as ZIP archives through GitHub Releases, not stored in the repository.

## Dataset Details

The dataset covers three varieties of Arabic plus a combined set:

| Variant | Description | Unique Word Types | Corpus Size (tokens) |
|---------|-------------|-------------------|----------------------|
| **CA** | Classical Arabic | 2.4M | 847M |
| **DA** | Dialectal Arabic (mixed dialects) | 6.7M | 5.8B |
| **MSA** | Modern Standard Arabic | 11.4M | 12.6B |
| **MIX** | Combined (CA + DA + MSA) | 16.1M | 17.3B |

### Data Format

- **File type**: Tab-separated values (`.tsv`), distributed as `.zip` archives
- **Column 1**: Arabic word (Arabic script)
- **Column 2**: Frequency count
- **Exclusions**: Digits, punctuation, and non-Arabic script tokens are excluded
- **Note**: Due to mixed text direction (RTL Arabic + LTR numbers), column order may appear reversed in some viewers

## License and Citation

- **License**: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) (Attribution-ShareAlike 4.0 International)
- **Requirement**: Users must cite the CAMeLBERT paper when using this data
- **Reference paper**: [CAMeLBERT (WANLP 2021)](https://aclanthology.org/2021.wanlp-1.10/)
- **Authors**: Khalifa, Inoue, Alhafni, Baimukan, Bouamor, Habash

## Development and Contribution Conventions

### No Development Tooling

This repository has **no**:
- Python packages, dependencies, or virtual environments
- Tests, linters, formatters, or type checkers
- CI/CD pipelines or GitHub Actions
- Makefile, Dockerfile, or build scripts
- Pre-commit hooks

### Commit Messages

Follow the existing convention: short, imperative-tense messages describing the change.

Examples from history:
- `Update README.md`
- `Create CITATION.cff`
- `Add LICENSE`

### What Changes Are Appropriate

Since this is a dataset metadata repository, changes are typically limited to:
- Updating `README.md` (documentation, download links, examples)
- Updating `CITATION.cff` (citation metadata)
- Updating `LICENSE.txt` (license terms)
- Adding metadata files as needed

### AI Assistant Guidelines

- Do not attempt to add build systems, test frameworks, or CI/CD pipelines unless explicitly requested
- Preserve the simplicity of the repository — it is intentionally minimal
- When editing `README.md`, preserve the Arabic text examples exactly as-is (RTL text handling matters)
- Respect the CC BY-SA 4.0 license requirements in any generated content
- The canonical upstream repository is `https://github.com/CAMeL-Lab/Camel_Arabic_Frequency_Lists`

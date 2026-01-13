# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Obsidian Knowledge Assistant is a command-line tool that analyzes Obsidian vaults (personal knowledge bases). It provides statistics, quality scoring, similarity analysis, and search capabilities to help users maintain healthy knowledge bases.

**Key characteristics:**
- Python 3.7+ (uses **only the Python standard library** - no external dependencies)
- Configuration-driven via shell script environment variables
- Modular architecture with separate CLI tools for different tasks
- Multi-vault support

## Essential Commands

### Configuration (Required First Step)

The vault path must be configured before running any analysis:

```bash
# Edit the configuration file (Windows: use Git Bash or WSL)
vim config/set_env.sh

# Then source it before running any Python script
source config/set_env.sh
```

**Critical configuration variable:** `VAULT_PATH` - must point to your Obsidian vault directory

### Running Analysis

```bash
# Full analysis pipeline (statistics + quality report + similarity detection)
python src/main.py

# Quality scoring standalone
python src/quality.py score              # Score all notes
python src/quality.py worst --limit 10   # Show 10 worst notes
python src/quality.py stats              # Quality statistics

# Search and exploration
python src/search.py search "python"                     # Keyword search
python src/search.py search --tags "programming,learn"  # Tag filter
python src/search.py orphans --limit 20                  # Find orphan notes
python src/search.py hubs --limit 10                     # Find knowledge hubs (high outbound links)
python src/search.py popular --limit 10                  # Find popular notes (high inbound links)

# Similarity analysis
python src/similar.py find "note_name"                  # Find notes similar to specific note
python src/similar.py duplicates --threshold 0.7        # Find potential duplicates
python src/similar.py unlinked --limit 20               # Find related but unlinked notes
```

### Quick Start Script

```bash
# Automatically loads config and runs main analysis
bash run.sh
```

## Architecture

### Core Data Flow

```
config/set_env.sh (shell env vars)
         ↓
main.py/quality.py/search.py/similar.py (CLI entry points)
         ↓
ObsidianAnalyzer.scan_vault() (two-pass scanning)
         ↓
Note dataclass[] (central data structure)
         ↓
[QualityScorer | SimilarityAnalyzer] (analysis modules)
         ↓
[ReportGenerator | DataExporter] (output layer)
```

### The Note Dataclass

All analysis revolves around the `Note` dataclass in `src/core/analyzer.py`:

```python
@dataclass
class Note:
    path: Path
    name: str
    content: str
    word_count: int
    outgoing_links: Set[str]  # Links from this note
    incoming_links: Set[str]  # Links to this note
    tags: Set[str]
    created_time: datetime
    modified_time: datetime
```

**Key properties:**
- `is_orphan`: True if note has no links in either direction
- `total_links`: Sum of incoming and outgoing links

### Two-Pass Scanning Strategy

`ObsidianAnalyzer.scan_vault()` uses two passes:
1. **Pass 1:** Parse all markdown files, extract outgoing links, tags, metadata
2. **Pass 2:** Build reverse index (incoming_links) by iterating through all outgoing links

This design enables efficient bidirectional link analysis without multiple file reads.

### Entry Point Responsibilities

- **main.py**: Orchestrates full pipeline (scan → quality score → export). Supports multi-vault analysis via `MultiVaultAnalyzer`
- **quality.py**: Standalone tool for quality assessment with subcommands (score, list, stats, worst, best, check)
- **search.py**: Multi-criteria filtering by keywords, tags, link counts. Identifies hubs (high outbound) and popular notes (high inbound)
- **similar.py**: TF-IDF + cosine similarity for finding duplicates, suggesting links, and merge recommendations

### Configuration Loading

Each entry point uses `load_env_from_file()` to parse `config/set_env.sh`:

```python
# Parses export VAR="value" statements
# Removes quotes for proper Python string handling
# Provides fallback values when config missing
```

**All behavior is controlled via environment variables** - no hardcoded paths or thresholds.

### Quality Scoring System

`QualityScorer` evaluates notes across four configurable dimensions (weights sum to 1.0):
- **Words** (default 0.25): Content depth, with minimum/ideal thresholds
- **Links** (default 0.35): Network connectivity, bidirectional preference
- **Tags** (default 0.15): Categorization coverage
- **Freshness** (default 0.25): Recency of updates

Generates letter grades (A-F) and specific improvement suggestions.

### Similarity Analysis

`SimilarityAnalyzer` uses TF-IDF vectorization with:
- **Content similarity** (60%): TF-IDF cosine similarity on note text
- **Title similarity** (20%): Title overlap
- **Tag similarity** (20%): Shared tags

Supports Chinese and English text with stopword filtering.

## Configuration Reference

Key environment variables in `config/set_env.sh`:

| Variable | Purpose | Default |
|----------|---------|---------|
| `VAULT_PATH` | Path to Obsidian vault | Required |
| `MULTI_VAULT_PATHS` | Comma-separated multiple vaults | Empty |
| `EXCLUDE_FOLDERS` | Folders to skip | `.obsidian,.trash,templates` |
| `EXPORT_JSON` | Export JSON data | `true` |
| `EXPORT_CSV` | Export CSV files | `true` |
| `ENABLE_QUALITY_SCORING` | Run quality analysis | `true` |
| `SCORE_WEIGHT_LINKS` | Link scoring weight | `0.35` |
| `SIMILARITY_MIN_THRESHOLD` | Minimum similarity | `0.3` |

## Development Notes

### Adding New Analysis Types

1. Create new module in `src/core/` following the pattern of `quality_scorer.py` or `similarity.py`
2. Accept `Dict[str, Note]` as input (the notes dictionary from `ObsidianAnalyzer`)
3. Return structured data for exporters to consume
4. Add CLI entry point (e.g., `src/new_tool.py`) if needed

### Adding Export Formats

Extend `src/exporters/exporter.py` (DataExporter) or `src/exporters/report_generator.py` (ReportGenerator).

### Testing Considerations

The codebase has no external dependencies. When adding tests:
- Use `unittest` from Python standard library
- Mock file I/O with `io.StringIO` or `tmpdir`
- Create sample vault structures in temporary directories

### Python Standard Library Usage

The project intentionally avoids `pip` dependencies. Common patterns:
- `argparse` for CLI interfaces
- `dataclasses` for structured data
- `pathlib` for path operations
- `re` for markdown parsing (links, tags)
- `collections.Counter` for statistics
- `datetime` for timestamps

## Link Format Handling

The analyzer supports several Obsidian link formats via regex:

- `[[note]]` - Basic link
- `[[note|alias]]` - Link with display text (strips to `note`)
- `[[note#heading]]` - Link to section (strips to `note`)
- `#tag` - Tags (extracted separately)

Links are stored as note names (strings), not full paths. Broken links (to non-existent notes) are preserved in `outgoing_links` but won't appear in any `incoming_links`.

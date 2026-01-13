# Quick Start Guide

Get started with Obsidian Knowledge Assistant in 5 minutes!

## Step 1: Download

```bash
git clone https://github.com/yourusername/obsidian-knowledge-assistant.git
cd obsidian-knowledge-assistant
```

## Step 2: Configure

Edit `config/set_env.sh` and set your vault path:

```bash
export VAULT_PATH="/path/to/your/obsidian/vault"
```

## Step 3: Run

```bash
# Load configuration
source config/set_env.sh

# Generate report
python src/main.py
```

That's it! Your reports will be in the `reports/` directory.

## Common Commands

```bash
# View quality scores
python src/quality.py score

# Find duplicates
python src/similar.py duplicates

# Search notes
python src/search.py search "keyword"

# Find orphans
python src/search.py orphans
```

## What's Next?

- Open the generated reports in your Obsidian vault
- Check out [docs/examples.md](docs/examples.md) for more workflows
- Read the full [documentation](docs/installation.md)

## Need Help?

- Check [docs/installation.md](docs/installation.md) for troubleshooting
- Open an [issue](https://github.com/yourusername/obsidian-knowledge-assistant/issues) on GitHub

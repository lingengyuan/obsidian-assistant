# Installation Guide

## System Requirements

- Python 3.7 or higher
- No external dependencies required (uses Python standard library only)
- Works on Windows, macOS, and Linux

## Quick Install

### Option 1: Clone from GitHub (Recommended)

```bash
git clone https://github.com/yourusername/obsidian-knowledge-assistant.git
cd obsidian-knowledge-assistant
```

### Option 2: Download ZIP

1. Download the latest release from [Releases](https://github.com/yourusername/obsidian-knowledge-assistant/releases)
2. Extract the ZIP file
3. Navigate to the extracted directory

## Configuration

### 1. Set up your vault path

Edit `config/set_env.sh` (or create `config/local.sh` for local overrides):

```bash
# Basic configuration
export VAULT_PATH="/path/to/your/obsidian/vault"

# Optional: Multiple vaults
export MULTI_VAULT_PATHS="/path/to/vault1,/path/to/vault2"
```

### 2. Load the configuration

#### On Linux/macOS:
```bash
source config/set_env.sh
```

#### On Windows (Git Bash):
```bash
source config/set_env.sh
```

#### On Windows (PowerShell):
Create a `config/set_env.ps1` file:
```powershell
$env:VAULT_PATH = "C:\path\to\your\obsidian\vault"
$env:REPORT_OUTPUT = "reports"
# ... other variables
```

Then load it:
```powershell
. .\config\set_env.ps1
```

## Verify Installation

Run a simple analysis to verify everything works:

```bash
python src/main.py --no-report
```

You should see output like:
```
============================================================
  Obsidian Knowledge Assistant
============================================================

🔍 Scanning vault: /path/to/vault
📝 Found 150 markdown files
✅ Analysis complete: 150 notes processed
...
```

## Optional: Add to PATH

### Linux/macOS

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export OBSIDIAN_ASSISTANT_HOME="/path/to/obsidian-knowledge-assistant"
alias oka="cd $OBSIDIAN_ASSISTANT_HOME && source config/set_env.sh"
```

Then you can run:
```bash
oka
python src/main.py
```

### Windows

Add the project directory to your PATH environment variable.

## Troubleshooting

### Python not found

Make sure Python 3.7+ is installed:

```bash
python --version
```

If not installed, download from [python.org](https://www.python.org/downloads/).

### Permission errors

On Linux/macOS, you may need to make scripts executable:

```bash
chmod +x src/*.py
```

### Encoding errors on Windows

If you see encoding errors, make sure your terminal is set to UTF-8:

```bash
chcp 65001  # Windows CMD
```

Or use Git Bash / WSL for better Unicode support.

### Module import errors

If you see `ModuleNotFoundError`, make sure you're running from the project root:

```bash
cd obsidian-knowledge-assistant
python src/main.py
```

## Next Steps

- Read the [Usage Guide](usage.md) to learn how to use the tool
- Check out [Examples](examples.md) for common workflows
- Explore [Configuration](configuration.md) for advanced options

## Uninstallation

Simply delete the project directory:

```bash
rm -rf obsidian-knowledge-assistant
```

If you added it to PATH, also remove those lines from your shell configuration files.

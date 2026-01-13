# Contributing to Obsidian Knowledge Assistant

First off, thank you for considering contributing to Obsidian Knowledge Assistant! 🎉

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues. When you are creating a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples**
- **Describe the behavior you observed and what you expected**
- **Include screenshots if relevant**
- **Include your environment details** (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

- **Use a clear and descriptive title**
- **Provide a detailed description of the suggested enhancement**
- **Explain why this enhancement would be useful**
- **List any alternative solutions you've considered**

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. If you've changed APIs, update the documentation
4. Ensure the test suite passes
5. Make sure your code follows the existing style
6. Issue that pull request!

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/obsidian-knowledge-assistant.git
cd obsidian-knowledge-assistant

# Create a branch
git checkout -b feature/my-new-feature

# Make your changes and test
python src/main.py --vault /path/to/test/vault

# Commit your changes
git add .
git commit -m "Add some feature"

# Push to your fork
git push origin feature/my-new-feature
```

## Coding Guidelines

### Python Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use meaningful variable names
- Add docstrings to functions and classes
- Keep functions focused and small
- Comment complex logic

### Project Structure

```
src/
├── core/           # Core analysis modules
│   ├── analyzer.py
│   ├── quality_scorer.py
│   └── similarity.py
├── exporters/      # Data export modules
│   ├── exporter.py
│   └── report_generator.py
└── *.py           # Command-line tools
```

### Adding a New Feature

1. **Core Module** - Add to `src/core/` if it's analysis logic
2. **CLI Tool** - Add to `src/` if it's a command-line interface
3. **Documentation** - Update relevant docs in `docs/`
4. **Tests** - Add tests in `tests/`
5. **Examples** - Add usage examples if applicable

### Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters
- Reference issues and pull requests liberally after the first line

Examples:
```
Add similarity analysis feature

- Implement TF-IDF vectorization
- Add cosine similarity calculation
- Create similar.py CLI tool

Closes #123
```

## Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_analyzer.py

# Run with coverage
python -m pytest --cov=src tests/
```

## Documentation

- Keep README.md up to date
- Update docs/ when adding new features
- Add docstrings to all public functions
- Include usage examples

## Questions?

Feel free to open an issue with your question or reach out to the maintainers.

## Recognition

Contributors will be recognized in:
- README.md Contributors section
- Release notes
- GitHub contributors page

Thank you for contributing! 🙏

# Contributing to YouTube Safety Inspector

Thanks for your interest in contributing! Here's how to get started.

## Ways to Contribute

### 🐛 Report Bugs
- Open an issue describing the bug
- Include steps to reproduce, expected vs actual behavior
- Add screenshots if relevant (especially for UI issues)

### 💡 Suggest Features
- Open an issue with the `enhancement` label
- Describe the feature and its use case
- Bonus: include mockups or examples

### 🔧 Submit Code

1. **Fork** the repository
2. **Clone** your fork locally
3. **Create a branch** for your feature/fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** and test locally
5. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add new safety category for X"
   ```
6. **Push** and open a Pull Request

## Development Setup

### Backend
```powershell
cd backend
pip install -r requirements.txt
$env:YOUTUBE_API_KEY = "your-api-key"
python main.py
```

### Extension
1. Open `chrome://extensions`
2. Enable Developer mode
3. Load unpacked → select `extension/` folder

## Code Style

- **Python**: Follow PEP 8, use meaningful variable names
- **JavaScript**: Use consistent indentation (2 spaces), prefer `const`/`let`
- **Commits**: Use conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)

## Adding Safety Signatures

Add new danger signatures to `safety-db/signatures/`:

```json
{
  "id": "unique-signature-id",
  "category": "Category Name",
  "patterns": ["pattern1", "pattern2"],
  "severity": "high",
  "description": "What makes this dangerous",
  "safe_alternative": "What to do instead"
}
```

## Adding Trusted Channels

Edit `backend/analyzer.py` and add channel names (lowercase) to `TRUSTED_CHANNELS`:

```python
TRUSTED_CHANNELS = [
    "bbc earth",
    "national geographic",
    # Add more here
]
```

## Adding Animal Keywords

Edit `backend/alternatives_finder.py` and add to `animal_keywords`:

```python
"new_animal": ["keyword1", "keyword2", "variant"],
```

## Questions?

Open an issue or start a discussion. We're happy to help!

#!/bin/sh
# Pre-commit hook to prevent API keys from being committed
# Place this in .git/hooks/pre-commit

# Patterns that look like API keys
FORBIDDEN_PATTERNS=(
    "AIzaSy"           # Google API keys
    "sk-[a-zA-Z0-9]"   # OpenAI keys
    "ghp_"             # GitHub tokens
    "api[_-]?key.*=.*['\"][a-zA-Z0-9]" # Generic API key assignments
)

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    # Check staged files for forbidden patterns
    if git diff --cached --name-only | xargs grep -l -E "$pattern" 2>/dev/null; then
        echo ""
        echo "🚨 BLOCKED: Possible API key detected!"
        echo "Pattern found: $pattern"
        echo ""
        echo "Files with potential secrets:"
        git diff --cached --name-only | xargs grep -l -E "$pattern" 2>/dev/null
        echo ""
        echo "Remove the secret and try again."
        exit 1
    fi
done

echo "✅ No API keys detected in commit"
exit 0

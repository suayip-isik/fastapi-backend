---
description: Analyze git changes since the last commit and suggest a commit message (does not commit)
allowed-tools: Bash
model: sonnet
---

Run the following commands and analyze the output:

1. `git status --short`
2. `git diff HEAD`
3. `git log -1 --oneline`

Based on the changes, write ONE commit message following these rules:

- Format: `type: short description` (conventional commits)
- Types: feat, fix, docs, chore, refactor, test, style, perf
- Imperative mood, all lowercase, no trailing period
- Max 250 characters
- Do NOT use double quotes anywhere in the message
- Do NOT include any author or co-author lines
- Do NOT make a commit — only output the message

Output ONLY the commit message, nothing else.

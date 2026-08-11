#!/usr/bin/env bash
# Clones the official and community "Claude Code" skill/agent/plugin
# repositories catalogued in claude-code-skills-research.md into a local
# directory for offline browsing and setup.
set -euo pipefail

DEST="${1:-./claude-code-resources}"
mkdir -p "$DEST"
cd "$DEST"

REPOS=(
  # Official Anthropic
  "https://github.com/anthropics/claude-code.git"
  "https://github.com/anthropics/skills.git"
  "https://github.com/anthropics/claude-plugins-official.git"
  "https://github.com/anthropics/claude-code-action.git"
  # Community awesome-lists
  "https://github.com/hesreallyhim/awesome-claude-code.git"
  "https://github.com/ComposioHQ/awesome-claude-skills.git"
  "https://github.com/travisvn/awesome-claude-skills.git"
  "https://github.com/GetBindu/awesome-claude-code-and-skills.git"
  "https://github.com/rohitg00/awesome-claude-code-toolkit.git"
  # Subagent collections
  "https://github.com/VoltAgent/awesome-claude-code-subagents.git"
  "https://github.com/supatest-ai/awesome-claude-code-sub-agents.git"
)

for repo in "${REPOS[@]}"; do
  name="$(basename "$repo" .git)"
  if [ -d "$name" ]; then
    echo "==> Updating $name"
    git -C "$name" pull --ff-only
  else
    echo "==> Cloning $name"
    git clone --depth 1 "$repo"
  fi
done

echo
echo "All repos are under: $(pwd)"
echo "Look for SKILL.md, .claude-plugin/plugin.json, and .claude/agents/*.md files inside each."

# Claude Code Skills, Plugins & Tools — GitHub Research

A structured map of where to find official and community "Claude Code" skills,
subagents, plugins, hooks, and configuration, plus copy-paste commands to pull
them all down locally.

Research date: 2026-08-11.

---

## 1. Official Anthropic repositories

| Repo | What it is | Stars (approx) |
|---|---|---|
| [`anthropics/claude-code`](https://github.com/anthropics/claude-code) | Claude Code CLI itself — source, `plugins/` (bundled first-party plugins), `.claude/commands/`, examples, changelog. | large |
| [`anthropics/skills`](https://github.com/anthropics/skills) | Official **Agent Skills** repo. `skills/` directory holds example + document skills (PDF/DOCX/PPTX/XLSX), `spec/` documents the Agent Skills open standard, `template/` is the scaffold for authoring a new skill. | large |
| [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official) | Anthropic-curated **plugin marketplace**. `plugins/` = Anthropic-maintained, `external_plugins/` = vetted third-party. Each plugin can bundle `commands/`, `agents/`, `skills/`, and `.mcp.json`. | 33k+ |
| [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action) | GitHub Action for running Claude Code against issues/PRs (the `@claude` mention integration). | — |

### Clone the official repos

```bash
git clone https://github.com/anthropics/claude-code.git
git clone https://github.com/anthropics/skills.git
git clone https://github.com/anthropics/claude-plugins-official.git
git clone https://github.com/anthropics/claude-code-action.git
```

### Install directly inside Claude Code (no manual cloning needed)

```bash
# Add the official skills marketplace, then install a bundle
/plugin marketplace add anthropics/skills
/plugin install document-skills@anthropic-agent-skills
/plugin install example-skills@anthropic-agent-skills

# Add the official plugin directory
/plugin marketplace add anthropics/claude-plugins-official
/plugin install {plugin-name}@claude-plugins-official
```

---

## 2. Community "awesome list" collections

These are curated indexes — read their README for a link farm to hundreds of
individual skill/agent repos, and clone the ones you want.

| Repo | Focus |
|---|---|
| [`hesreallyhim/awesome-claude-code`](https://github.com/hesreallyhim/awesome-claude-code) | The largest general index (52k+ stars): skills, slash commands, hooks, status lines, plugins, alt clients, agent orchestration, security, observability — organized into ~15 categories. |
| [`ComposioHQ/awesome-claude-skills`](https://github.com/ComposioHQ/awesome-claude-skills) | 1000+ production skills across document processing, dev/code, data, business, creative, security, and 78 pre-built "app automation" workflows (Slack, Gmail, Notion, GitHub, Salesforce, etc.). |
| [`travisvn/awesome-claude-skills`](https://github.com/travisvn/awesome-claude-skills) | Similar curated skills list, smaller/independent from Composio's. |
| [`GetBindu/awesome-claude-code-and-skills`](https://github.com/GetBindu/awesome-claude-code-and-skills) | Combined Claude Code + Skills collection. |
| [`rohitg00/awesome-claude-code-toolkit`](https://github.com/rohitg00/awesome-claude-code-toolkit) | Single-repo "everything toolkit": 135 agents, 35 skills (+400k via SkillKit), 42 commands, 176+ plugins, 20 hooks, 15 rules, 7 templates, 14 MCP configs, companion apps — all under one root. |

```bash
git clone https://github.com/hesreallyhim/awesome-claude-code.git
git clone https://github.com/ComposioHQ/awesome-claude-skills.git
git clone https://github.com/travisvn/awesome-claude-skills.git
git clone https://github.com/GetBindu/awesome-claude-code-and-skills.git
git clone https://github.com/rohitg00/awesome-claude-code-toolkit.git
```

---

## 3. Subagent collections

| Repo | Focus |
|---|---|
| [`VoltAgent/awesome-claude-code-subagents`](https://github.com/VoltAgent/awesome-claude-code-subagents) | 154+ subagents in 10 categories: core dev, language specialists, infrastructure, quality/security, data/AI, dev experience, specialized domains, business/product, meta-orchestration, research/analysis. Ships an installer script. |
| [`supatest-ai/awesome-claude-code-sub-agents`](https://github.com/supatest-ai/awesome-claude-code-sub-agents) | Another curated subagent collection. |

```bash
git clone https://github.com/VoltAgent/awesome-claude-code-subagents.git
cd awesome-claude-code-subagents
./install-agents.sh          # interactive installer → ~/.claude/agents or ./.claude/agents

# or, without cloning:
curl -sO https://raw.githubusercontent.com/VoltAgent/awesome-claude-code-subagents/main/install-agents.sh
chmod +x install-agents.sh && ./install-agents.sh

# or via the plugin marketplace
claude plugin install voltagent-core-dev
claude plugin install voltagent-lang
claude plugin install voltagent-infra
```

---

## 4. Directory layout you'll find inside these repos

**A skill** (`anthropics/skills` style, and the format used almost everywhere):

```
skill-name/
└── SKILL.md          # YAML frontmatter (name, description) + instructions
    scripts/           # optional helper scripts the skill can invoke
    references/        # optional reference docs loaded on demand
```

**A plugin** (`claude-plugins-official` / most marketplace plugins):

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json    # required metadata
├── .mcp.json           # optional MCP server config
├── commands/           # optional slash commands
├── agents/             # optional subagent definitions
├── skills/             # optional bundled skills
└── README.md
```

**A subagent** is a single Markdown file with YAML frontmatter (`name`,
`description`, `tools`) dropped into `.claude/agents/` (project) or
`~/.claude/agents/` (global) — that's the whole format, no build step.

---

## 5. Where things get installed locally

| Type | Project-scope path | User-scope path |
|---|---|---|
| Skills | `.claude/skills/` | `~/.claude/skills/` |
| Subagents | `.claude/agents/` | `~/.claude/agents/` |
| Slash commands | `.claude/commands/` | `~/.claude/commands/` |
| Plugins (via marketplace) | managed by `claude plugin` | `~/.claude/plugins/` |
| Settings/hooks | `.claude/settings.json` | `~/.claude/settings.json` |

Claude Code discovers anything dropped in those directories automatically —
no registration step beyond having the file present in the right place.

---

## 6. One-shot script to pull everything down

Save as `clone-claude-code-resources.sh` and run — it clones every repo above
into `./claude-code-resources/`.

```bash
#!/usr/bin/env bash
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
```

```bash
chmod +x clone-claude-code-resources.sh
./clone-claude-code-resources.sh
```

---

## 7. Quick-start: wiring the results into a project

```bash
# Skills — copy into project scope
mkdir -p .claude/skills
cp -r claude-code-resources/anthropics-skills/skills/example-skills/* .claude/skills/

# Subagents — copy into project scope
mkdir -p .claude/agents
cp claude-code-resources/awesome-claude-code-subagents/categories/**/*.md .claude/agents/

# Plugins — prefer the in-CLI marketplace flow over manual copying
/plugin marketplace add anthropics/claude-plugins-official
/plugin marketplace add rohitg00/awesome-claude-code-toolkit
/plugin install <plugin-name>@<marketplace-name>
```

---

## 8. Notes / caveats

- **Trust before installing.** Anthropic explicitly disclaims verification of
  third-party plugin contents in `claude-plugins-official/external_plugins`;
  review `commands/`, `agents/`, and any `.mcp.json` before installing
  anything that runs shell commands or reaches external services.
- **Duplication across lists.** The awesome-lists overlap heavily — the same
  individual skill/agent repo is often linked from three or four of them.
  Clone the awesome-lists first, skim their READMEs, then selectively clone
  only the individual repos you actually want rather than cloning everything
  transitively.
- **Agent Skills is now an open standard** (agentskills.io, published
  December 2025), so `SKILL.md`-format skills from `anthropics/skills` also
  work in GitHub Copilot, Cursor, OpenAI Codex, Gemini CLI, and others — not
  Claude-Code-exclusive.

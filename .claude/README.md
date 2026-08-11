# `.claude/` Contents & Provenance

This directory holds every skill, subagent, and command mirrored into this
repo, plus a custom quant-trading persona layer built on top of them. This
file is the manifest: what's here, where it came from, and its license.

Total files under `.claude/`: 614.

```
.claude/
├── skills/                              (19 skills)
│   ├── market-structure-detection/      ← original, this repo (BOS/CHoCH/order-block/FVG rules)
│   ├── pine-script-strategy-builder/    ← original, this repo (Pine v6 skeletons)
│   └── <17 more>                        ← anthropics/skills (skills/skills/*)
│
├── agents/
│   ├── quant-trading/                   (5 agents, original, this repo)
│   │   ├── pine-script-developer.md
│   │   ├── market-structure-analyst.md
│   │   ├── algo-trading-strategist.md
│   │   ├── quant-backtest-engineer.md
│   │   └── broker-api-integration-specialist.md
│   │
│   ├── official/                        (15 agents ← anthropics/claude-code, plugins/*/agents/)
│   │   ├── agent-sdk-dev/               agent-sdk-verifier-py.md, agent-sdk-verifier-ts.md
│   │   ├── feature-dev/                 code-architect.md, code-explorer.md, code-reviewer.md
│   │   ├── hookify/                     conversation-analyzer.md
│   │   ├── plugin-dev/                  agent-creator.md, plugin-validator.md, skill-reviewer.md
│   │   └── pr-review-toolkit/           code-reviewer.md, code-simplifier.md, comment-analyzer.md,
│   │                                     pr-test-analyzer.md, silent-failure-hunter.md,
│   │                                     type-design-analyzer.md
│   │
│   └── community/                       (154 agents ← VoltAgent/awesome-claude-code-subagents, categories/*)
│       ├── 01-core-development/         11 agents (frontend/backend/fullstack/mobile/API)
│       ├── 02-language-specialists/     30 agents (per-language experts)
│       ├── 03-infrastructure/           16 agents (DevOps/cloud/K8s/deployment)
│       ├── 04-quality-security/         17 agents (testing/security/compliance)
│       ├── 05-data-ai/                  13 agents (ML/data engineering/AI systems)
│       ├── 06-developer-experience/     15 agents (tooling/docs/DX)
│       ├── 07-specialized-domains/      14 agents (blockchain/fintech/healthcare/IoT)
│       ├── 08-business-product/         16 agents (product/business analysis)
│       ├── 09-meta-orchestration/       11 agents (agent coordination/workflow)
│       └── 10-research-analysis/        11 agents (research/trend/competitive analysis)
│           (each category dir also keeps its upstream README.md)
│
└── commands/
    └── official/                        (15 commands ← anthropics/claude-code, plugins/*/commands/)
        ├── agent-sdk-dev/               new-sdk-app.md
        ├── code-review/                 code-review.md
        ├── commit-commands/             clean_gone.md, commit-push-pr.md, commit.md
        ├── feature-dev/                 feature-dev.md
        ├── hookify/                     configure.md, help.md, hookify.md, list.md
        ├── plugin-dev/                  create-plugin.md
        ├── pr-review-toolkit/           review-pr.md
        └── ralph-wiggum/                cancel-ralph.md, help.md, ralph-loop.md
```

## Source repositories & licenses

| Local path | Upstream repo | License |
|---|---|---|
| `.claude/skills/*` (17 dirs, all except the two `original` ones) | [`anthropics/skills`](https://github.com/anthropics/skills), `skills/` subdir | Anthropic (see each skill's own `LICENSE.txt` where present; repo also ships `THIRD_PARTY_NOTICES.md`) |
| `.claude/agents/official/*`, `.claude/commands/official/*` | [`anthropics/claude-code`](https://github.com/anthropics/claude-code), `plugins/*/agents/` and `plugins/*/commands/` | © Anthropic PBC — Commercial Terms of Service |
| `.claude/agents/community/*` | [`VoltAgent/awesome-claude-code-subagents`](https://github.com/VoltAgent/awesome-claude-code-subagents), `categories/` | MIT License, © 2025 VoltAgent |
| `.claude/skills/market-structure-detection/`, `.claude/skills/pine-script-strategy-builder/`, `.claude/agents/quant-trading/*` | original — authored in this repo for the quant-trading persona | same license as this repo |

Files were copied as-is from a shallow (`--depth 1`) clone of each upstream
repo at the commit current on 2026-08-11; no upstream content was modified.

## Not mirrored (by design)

To keep this repo reviewable, the following were **not** copied wholesale —
see `claude-code-skills-research.md` at the repo root for how to pull them if
needed:

- `anthropics/claude-plugins-official` `external_plugins/` (large, mixed
  trust — install selectively via `/plugin marketplace add` instead)
- `ComposioHQ/awesome-claude-skills` and other 1000+-skill community
  collections
- The rest of the `awesome-claude-code-toolkit` (176+ plugins, hooks, rules,
  templates, MCP configs)

## Regenerating / updating this mirror

```bash
SRC=/tmp/claude-code-src   # any scratch dir
git clone --depth 1 https://github.com/anthropics/skills.git "$SRC/skills"
git clone --depth 1 https://github.com/anthropics/claude-code.git "$SRC/claude-code"
git clone --depth 1 https://github.com/VoltAgent/awesome-claude-code-subagents.git "$SRC/awesome-claude-code-subagents"

# Skills
cp -r "$SRC/skills/skills/." .claude/skills/

# Official plugin agents + commands
for d in "$SRC/claude-code/plugins"/*/; do
  plugin=$(basename "$d")
  [ -d "$d/agents" ]   && mkdir -p ".claude/agents/official/$plugin"   && cp "$d/agents/"*.md   ".claude/agents/official/$plugin/"
  [ -d "$d/commands" ] && mkdir -p ".claude/commands/official/$plugin" && cp "$d/commands/"*.md ".claude/commands/official/$plugin/"
done

# Community subagents
cp -r "$SRC/awesome-claude-code-subagents/categories/." .claude/agents/community/
```

The `quant-trading/` agents and the two original skills are hand-authored —
re-running the script above will not touch them.

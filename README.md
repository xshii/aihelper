# aihelper

A skill library and teaching corpus for a weaker AI. Strong AI (Claude etc.) produces demos, skills, and prompts here; the weaker AI consumes them to level up.

## What's In This Repo

| Type | Prefix | Purpose |
|------|--------|---------|
| **Skill** | `skill-*` | Structured skill definitions with prompts + examples |
| **Demo** | `demo-*` | Runnable reference code the AI can imitate |
| **Prompt** | `prompt-*` | Standalone prompts for specific tasks |
| **Tool** | `tool-*` | Utility tools (traditional code) |

## Quick Start

```bash
# Install just (task runner)
brew install just

# Create a new skill
just new skill-code-review

# Create a new demo
just new demo-cli-tool

# List all projects
just list

# Validate catalog
just catalog-check
```

## How to Use a Skill

For the weaker AI's operator:

1. Find the skill in [CATALOG.md](CATALOG.md)
2. Open its `PROMPT.md` — this is the ready-to-use prompt
3. Copy-paste into the weaker AI's context
4. Optionally include `examples/` for few-shot learning
5. For deeper understanding, read `SKILL.md`

## Structure

```
projects/
  skill-*/       Skill definitions (PROMPT.md + SKILL.md + examples/)
  demo-*/        Reference implementations
  prompt-*/      Standalone prompts
  tool-*/        Utility tools
shared/          Shared code (only when 2+ projects need it)
CATALOG.md       Project index
CLAUDE.md        AI assistant constitution
```

## Design Philosophy

**Progressive Disclosure (渐进式暴露):** Everything is layered — the weaker AI's operator can give it just a PROMPT.md (Layer 0), add examples (Layer 1), include the full SKILL.md (Layer 2), or point it at demo code (Layer 3).

See [CLAUDE.md](CLAUDE.md) for the full philosophy and methodology.

## Project Catalog

See [CATALOG.md](CATALOG.md).

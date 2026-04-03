# CLAUDE.md

## Repository Structure
This is a polyglot monorepo of unrelated utility projects.
All projects live under `projects/`. Each is fully self-contained.

## Conventions
- Every project MUST have a `README.md` and `project.yaml`
- Project READMEs must include: purpose, prerequisites, how to run
- Do not create cross-project dependencies unless absolutely necessary
- If shared code emerges, put it in `shared/` (requires 2+ consumers)
- Use `just new <name>` to scaffold a new project

## Working on a Project
- cd into `projects/<name>` and treat it as an independent repo
- Each project defines its own language, deps, and tooling
- Check `project.yaml` for status and metadata

## Adding a New Project
1. Run `just new <project-name>`
2. Edit `projects/<project-name>/project.yaml` with real metadata
3. Write the project code
4. Update `CATALOG.md` with a one-line entry

## project.yaml Schema
```yaml
name: string          # Project name (same as directory name)
description: string   # One-line description
language: string      # Primary language (python, typescript, go, shell, etc.)
tags: [string]        # Free-form tags for discovery
status: string        # active | experimental | archived
created: date         # YYYY-MM-DD
```

## Rules
- No root-level package.json, pyproject.toml, or go.work
- No root-level pre-commit hooks — projects manage their own linting
- No nested categories — use tags in project.yaml instead of directory hierarchy
- Do not extract into shared/ until at least two projects need it

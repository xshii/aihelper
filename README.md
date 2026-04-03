# aihelper

A polyglot monorepo for miscellaneous AI-assisted utility projects. Each project under `projects/` is fully self-contained with its own dependencies, tooling, and documentation.

## Quick Start

```bash
# Install just (task runner) - https://github.com/casey/just
brew install just

# Create a new project
just new my-project

# List all projects
just list

# Validate catalog
just catalog-check
```

## Structure

```
projects/          All projects live here, flat structure
  _template/       Copy this to start a new project
  <project>/       Each project is independent
shared/            Shared utilities (only when 2+ projects need it)
CATALOG.md         Human-readable project index
justfile           Common operations
```

## Adding a New Project

1. `just new <project-name>`
2. Edit `projects/<project-name>/project.yaml` with real metadata
3. Write your code
4. Add a one-line entry to [CATALOG.md](CATALOG.md)

## Project Catalog

See [CATALOG.md](CATALOG.md) for a full list of projects.

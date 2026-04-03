# aihelper task runner
# Install: brew install just (macOS) or see https://github.com/casey/just

# List all projects with their status
list:
    @echo "Projects:"
    @echo "========="
    @for dir in projects/*/; do \
        name=$(basename "$dir"); \
        if [ "$name" = "_template" ]; then continue; fi; \
        if [ -f "$dir/project.yaml" ]; then \
            type=$(grep '^type:' "$dir/project.yaml" | awk '{print $2}'); \
            status=$(grep '^status:' "$dir/project.yaml" | awk '{print $2}'); \
            desc=$(grep '^description:' "$dir/project.yaml" | sed 's/^description: *//'); \
            printf "  %-25s [%-6s] [%s] %s\n" "$name" "$type" "$status" "$desc"; \
        else \
            printf "  %-25s [no metadata]\n" "$name"; \
        fi; \
    done

# List projects filtered by type
list-type type:
    @for dir in projects/*/; do \
        name=$(basename "$dir"); \
        if [ "$name" = "_template" ]; then continue; fi; \
        if [ -f "$dir/project.yaml" ]; then \
            t=$(grep '^type:' "$dir/project.yaml" | awk '{print $2}'); \
            if [ "$t" = "{{type}}" ]; then \
                desc=$(grep '^description:' "$dir/project.yaml" | sed 's/^description: *//'); \
                printf "  %-25s %s\n" "$name" "$desc"; \
            fi; \
        fi; \
    done

# Create a new project from template
new name:
    @if [ -d "projects/{{name}}" ]; then \
        echo "Error: projects/{{name}} already exists"; \
        exit 1; \
    fi
    cp -r projects/_template "projects/{{name}}"
    @sed -i '' 's/^name: .*/name: {{name}}/' "projects/{{name}}/project.yaml"
    @sed -i '' 's/^created: .*/created: '"$(date +%Y-%m-%d)"'/' "projects/{{name}}/project.yaml"
    @sed -i '' 's/# Project Name/# {{name}}/' "projects/{{name}}/README.md"
    @# Detect type from prefix
    @type=$(echo "{{name}}" | sed 's/-.*//' ); \
    if echo "skill demo prompt tool" | grep -qw "$type"; then \
        sed -i '' "s/^type: .*/type: $type/" "projects/{{name}}/project.yaml"; \
    fi
    @echo "Created projects/{{name}}"
    @echo ""
    @echo "Next steps:"
    @echo "  1. Edit projects/{{name}}/project.yaml"
    @echo "  2. Write PROMPT.md — the most important deliverable"
    @echo "  3. Add examples to examples/"
    @echo "  4. Update CATALOG.md"

# Check that CATALOG.md is in sync with project directories
catalog-check:
    @echo "Checking catalog..."
    @errors=0; \
    for dir in projects/*/; do \
        name=$(basename "$dir"); \
        if [ "$name" = "_template" ]; then continue; fi; \
        if ! grep -q "| $name " CATALOG.md 2>/dev/null && ! grep -q "| $name|" CATALOG.md 2>/dev/null; then \
            echo "MISSING in CATALOG.md: $name"; \
            errors=$((errors + 1)); \
        fi; \
    done; \
    if [ "$errors" -eq 0 ]; then \
        echo "All projects are listed in CATALOG.md"; \
    else \
        echo "$errors project(s) missing from CATALOG.md"; \
        exit 1; \
    fi

# Validate required files for each project
validate:
    @echo "Validating projects..."
    @errors=0; \
    for dir in projects/*/; do \
        name=$(basename "$dir"); \
        if [ "$name" = "_template" ]; then continue; fi; \
        if [ ! -f "$dir/project.yaml" ]; then \
            echo "MISSING: $name/project.yaml"; \
            errors=$((errors + 1)); \
        fi; \
        if [ ! -f "$dir/README.md" ]; then \
            echo "MISSING: $name/README.md"; \
            errors=$((errors + 1)); \
        fi; \
        type=$(grep '^type:' "$dir/project.yaml" 2>/dev/null | awk '{print $2}'); \
        if [ "$type" = "skill" ] || [ "$type" = "prompt" ]; then \
            if [ ! -f "$dir/PROMPT.md" ]; then \
                echo "MISSING: $name/PROMPT.md (required for type=$type)"; \
                errors=$((errors + 1)); \
            fi; \
        fi; \
        if [ "$type" = "skill" ] && [ ! -f "$dir/SKILL.md" ]; then \
            echo "MISSING: $name/SKILL.md (required for type=skill)"; \
            errors=$((errors + 1)); \
        fi; \
    done; \
    if [ "$errors" -eq 0 ]; then \
        echo "All projects pass validation"; \
    else \
        echo "$errors issue(s) found"; \
        exit 1; \
    fi

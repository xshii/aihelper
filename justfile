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
            status=$(grep '^status:' "$dir/project.yaml" | awk '{print $2}'); \
            desc=$(grep '^description:' "$dir/project.yaml" | sed 's/^description: *//'); \
            printf "  %-20s [%s] %s\n" "$name" "$status" "$desc"; \
        else \
            printf "  %-20s [no metadata]\n" "$name"; \
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
    @echo "Created projects/{{name}}"
    @echo "Next steps:"
    @echo "  1. Edit projects/{{name}}/project.yaml"
    @echo "  2. Write your code"
    @echo "  3. Add entry to CATALOG.md"

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

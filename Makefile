.PHONY: lint test check-imports verify

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest tests/ || [ $$? -eq 5 ]

# Enforce the core import boundary: core/ must never import from domains/.
# Run this before every commit or in CI.
check-imports:
	@echo "Checking core/ does not import from domains/..."
	@if grep -r "from domains" core/ 2>/dev/null; then \
		echo "ERROR: core/ imports from domains/ — this violates the architecture boundary."; \
		exit 1; \
	else \
		echo "OK: no boundary violations found."; \
	fi

# Run all checks
verify: check-imports lint test

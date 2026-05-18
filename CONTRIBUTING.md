# Contributing to GreenSignal

## Ground rules

- **Never push directly to `main`.** It is protected — all changes go through a pull request.
- **Every PR needs one approving review** before it can be merged. The author cannot merge their own PR without the other person approving.
- **Stale approvals are dismissed automatically.** If you push new commits after someone approves, they need to re-approve.
- **No force-pushes to `main`.** This is enforced by GitHub.

## Day-to-day workflow

```bash
# 1. Start from a fresh main
git checkout main && git pull

# 2. Create a branch — name it after what you're doing
git checkout -b feat/ice-price-source
# or: fix/enso-parser-year-boundary
# or: data/usda-psd-validation

# 3. Do your work, commit regularly
git add <files>
git commit -m "brief description of what and why"

# 4. Before opening a PR, verify everything passes
make verify

# 5. Push and open a PR
git push -u origin feat/ice-price-source
gh pr create --fill
```

## Branch naming

| Prefix | Use for |
|--------|---------|
| `feat/` | New source, feature, or route |
| `fix/` | Bug fix |
| `data/` | Notebook work or data validation |
| `docs/` | Documentation changes only |
| `chore/` | Dependency updates, config changes |

## Commit messages

One line, present tense, lowercase:

```
add noaa_enso source with fixed-width parser
fix cot index rolling window off-by-one
validate usda psd signals against phase 0 gates
```

## Secrets — read carefully

- **Never commit `.env`** — it is gitignored and must stay that way.
- API keys, Supabase credentials, and GEE tokens live in `.env` only.
- Use `.env.example` to document which keys exist (no values).
- If you accidentally commit a secret: rotate the key immediately, then remove it from git history.

## Running checks locally

```bash
make verify          # import boundary + lint + tests — run before every PR
make check-imports   # core/ must never import from domains/
make lint            # ruff
make test            # pytest
```

## Notebooks

Notebooks in `notebooks/coffee_backtests/` must be run in order (01 → 06) and all pass the gates in `notebooks/coffee_backtests/README.md` before any API or frontend work begins. Commit notebooks with output cleared unless the output is the point (e.g. a validated correlation table).

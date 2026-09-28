#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-Mrbaeksang/starcraft-ai}"
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"
PAGES_URL="https://${OWNER,,}.github.io/${NAME}/"

command -v gh >/dev/null || {
  echo "GitHub CLI (gh) is required." >&2
  exit 1
}

gh auth status >/dev/null

echo "Configuring repository metadata..."
gh api --method PATCH "repos/$REPO" --input - <<JSON
{
  "description": "Open research on structured latent world models, planning, and self-improving agents for StarCraft: Brood War.",
  "homepage": "$PAGES_URL",
  "has_issues": true,
  "has_projects": true,
  "has_wiki": false,
  "has_discussions": true,
  "allow_squash_merge": true,
  "allow_merge_commit": false,
  "allow_rebase_merge": true,
  "allow_auto_merge": true,
  "delete_branch_on_merge": true,
  "allow_update_branch": true
}
JSON

echo "Configuring topics..."
gh api --method PUT "repos/$REPO/topics" --input - <<'JSON'
{
  "names": [
    "starcraft",
    "brood-war",
    "bwapi",
    "artificial-intelligence",
    "reinforcement-learning",
    "model-based-rl",
    "world-model",
    "jepa",
    "pytorch",
    "self-play",
    "planning",
    "representation-learning"
  ]
}
JSON

echo "Creating/updating labels..."
labels=(
  "area:data|0e8a16|Replay, dataset, schema, and provenance work"
  "area:model|5319e7|Model architecture and training"
  "area:planning|1d76db|Planning and control"
  "area:infra|0052cc|CI, packaging, tooling, and infrastructure"
  "research|d4c5f9|Research hypothesis or experiment"
  "benchmark|fbca04|Benchmarking and evaluation"
  "reproducibility|bfdadc|Reproducibility and experiment tracking"
  "blocked|b60205|Blocked by an external dependency or prior milestone"
)
for item in "${labels[@]}"; do
  IFS='|' read -r label color description <<< "$item"
  gh label create "$label" --repo "$REPO" --color "$color" --description "$description" --force
done

echo "Protecting main from force-push/deletion while preserving trusted automation..."
gh api --method PUT "repos/$REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON

echo "Enabling GitHub Pages workflow mode..."
if gh api "repos/$REPO/pages" >/dev/null 2>&1; then
  gh api --method PUT "repos/$REPO/pages" -f build_type=workflow >/dev/null
else
  gh api --method POST "repos/$REPO/pages" -f build_type=workflow >/dev/null
fi

echo "Triggering the Pages deployment..."
gh workflow run pages.yml --repo "$REPO"

echo
echo "Repository bootstrap complete."
echo "Homepage: $PAGES_URL"

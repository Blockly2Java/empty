#!/usr/bin/env bash
# Clones sub-repos alongside this directory for local development.
# Run once after cloning the top-level repo.
# Self-discovering: derives org and exercise name from git remote — no editing needed.
set -e

# Derive org and exercise name from the git remote of THIS repo
REMOTE_URL=$(git remote get-url origin)
# Handles both SSH (git@github.com:Org/Repo.git) and HTTPS (https://github.com/Org/Repo.git)
ORG=$(echo "$REMOTE_URL" | sed -E 's|.*[:/]([^/]+)/[^/]+\.git.*|\1|')
EXERCISE=$(echo "$REMOTE_URL" | sed -E 's|.*[:/][^/]+/([^/]+)\.git.*|\1|')

echo "Organisation : $ORG"
echo "Exercise     : $EXERCISE"
echo ""

BASE="git@github.com:${ORG}"

for sub in solution template tests; do
  if [ ! -d "$sub/.git" ]; then
    echo "Cloning ${EXERCISE}_${sub}..."
    git clone "${BASE}/${EXERCISE}_${sub}.git" "$sub"
  else
    echo "$sub already present, pulling latest..."
    git -C "$sub" pull --ff-only
  fi
done
echo ""
echo "Done! Run './gradlew testSolution' to verify."

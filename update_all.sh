#!/bin/bash

# Script to commit, push subfolders and update submodules in parent repo

set -e  # Exit on error

# Array of subdirectories that are git repositories
SUBDIRS=("solution" "template" "tests")

echo "=== Starting update process ==="

# Process each subdirectory
for dir in "${SUBDIRS[@]}"; do
    if [ -d "$dir/.git" ]; then
        echo ""
        echo "--- Processing $dir ---"
        cd "$dir"

        # Check if there are changes
        if [[ -n $(git status -s) ]]; then
            echo "Changes detected in $dir"
            git add .
            git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S')"
            git push
            echo "Committed and pushed $dir"
        else
            echo "No changes in $dir"
            # Try to push anyway in case there are unpushed commits
            if [[ $(git rev-list @{u}.. 2>/dev/null | wc -l) -gt 0 ]]; then
                echo "Pushing unpushed commits in $dir"
                git push
            fi
        fi

        cd ..
    else
        echo "Warning: $dir is not a git repository"
    fi
done

# Update parent repository to track new submodule commits
echo ""
echo "--- Updating parent repository ---"

# Check if there are submodule changes
if [[ -n $(git status -s | grep -E "^\s*M\s+(solution|template|tests)") ]]; then
    echo "Submodule changes detected, updating parent repository"
    git add solution template tests
    git commit -a -m "Update submodules to latest commits"
    git push
    echo "Parent repository updated"
else
    echo "No submodule changes to commit"
    git commit -a -m "Update non-submodule changes" || echo "No non-submodule changes to commit"
    git push
fi

echo ""
echo "=== Update process complete ==="

#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 v1.0.1"
  exit 1
fi

VERSION=$1

echo "==> Checking git status..."
git fetch --all --tags
git status

echo "==> Creating tag $VERSION..."
git tag $VERSION

echo "==> Pushing tag $VERSION to origin..."
git push origin $VERSION

echo "==> Done! Tag $VERSION created and pushed."

# run the following in terminal and adjust the version number: ./scripts/bump_version.sh v1.0.1
# to delete an existing version: git tag -d v1.0.1    
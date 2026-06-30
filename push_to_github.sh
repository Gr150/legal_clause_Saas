#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Claura — push to GitHub
# Run this once to set up the repo and push everything
#
# Usage:
#   chmod +x push_to_github.sh
#   ./push_to_github.sh YOUR-GITHUB-USERNAME
# ──────────────────────────────────────────────────────────────

set -e

GITHUB_USERNAME=${1:-"YOUR-USERNAME"}
REPO_NAME="claura"
REPO_URL="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

echo ""
echo "Pushing Claura to GitHub"
echo "Username: ${GITHUB_USERNAME}"
echo "Repo:     ${REPO_URL}"
echo ""

# Step 1 — initialise git
git init
git config user.name "${GITHUB_USERNAME}"
git config user.email "${GITHUB_USERNAME}@users.noreply.github.com"

# Step 2 — add everything
git add .
git commit -m "Initial commit — Claura frontend and backend

- Login portal and dashboard (HTML/CSS)
- FastAPI backend with auth, upload, analyse, results routes
- Mistral 7B LoRA model integration (HuggingFace)
- PostgreSQL database with SQLAlchemy async
- JWT authentication
- PyMuPDF clause extraction
- Docker Compose for local development
- HITL correction endpoint for model improvement"

# Step 3 — push
git branch -M main
git remote add origin ${REPO_URL}
git push -u origin main

echo ""
echo "Done. Visit: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"

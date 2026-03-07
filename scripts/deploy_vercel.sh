#!/usr/bin/env bash
set -euo pipefail

if ! command -v vercel >/dev/null 2>&1; then
  echo "vercel CLI not found. Install with: npm i -g vercel"
  exit 1
fi

echo "Linking project (interactive if first run)..."
vercel link

echo "Deploying to production..."
vercel --prod

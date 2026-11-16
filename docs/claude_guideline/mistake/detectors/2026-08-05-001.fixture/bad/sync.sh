#!/bin/bash
cd "$REPO"
git stash
git reset --hard origin/main

#!/bin/bash
cd "$REPO"
git stash push -- docs/
git checkout -- docs/x.md

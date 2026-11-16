#!/usr/bin/env bash
grep -rn "TODO" "${1:-.}" && exit 1 || exit 0

#!/usr/bin/env python3
import subprocess

log = subprocess.check_output(
    ["git", "log", "--pretty=format:- %s (%h)", "HEAD~50..HEAD"],
    text=True,
)
print("# Release notes\n")
print(log)

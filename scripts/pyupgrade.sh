#!/bin/bash

# Upgrade syntax of all python files under nomad/ folder using pyupgrade
# pyupgrade is not installed by default
# install it using `pip install pyupgrade` or `uv pip install pyupgrade`
# using modern syntax to maximise maintainability and readability
# it is also possible to use pyupgrade as a commit hook

if ! command -v pyupgrade &> /dev/null; then
    echo "Error: pyupgrade is not installed. Please install it using 'pip install pyupgrade'."
    exit 1
fi

# Navigate to the parent folder based on script location
cd "$(dirname "$0")/.." || exit 1

# Find all Python files in the "nomad" folder and apply pyupgrade
find nomad -type f -name "*.py" | while read -r file; do
    pyupgrade --py310-plus "$file"
done

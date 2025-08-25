#!/bin/sh
set -e

cd "$(dirname "$(dirname "$(realpath "$0")")")"

# Clean up any previous build
rm -rf nomad/app/static/gui
rm -rf site nomad_lab.egg-info dist build

cd gui
yarn --network-timeout 1200000
yarn run build
cd ..
mkdir -p nomad/app/static/gui
cp -r gui/build/* nomad/app/static/gui

python -m build --sdist

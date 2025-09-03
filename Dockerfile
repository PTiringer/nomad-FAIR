#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/engine/reference/builder/

# ================================================================================
# GUI cached base layers
# ================================================================================

# node20 image local copy
FROM gitlab-registry.mpcdf.mpg.de/nomad-lab/nomad-fair:node AS base_node

RUN mkdir -p /app/gui
WORKDIR /app/gui

ENV PATH=/app/node_modules/.bin:$PATH
ENV NODE_OPTIONS="--max_old_space_size=4096 --openssl-legacy-provider"

# ================================================================================
# Python cached base layers
# ================================================================================

FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS base_python
# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/backend/"
ENV UV_SYSTEM_PYTHON=1
ENV UV_NO_CACHE=1

RUN apt-get update \
     && apt-get install --yes --quiet --no-install-recommends \
     build-essential \
     curl \
     file \
     gcc \
     git \
     libgomp1 \
     libmagic1 \
     unzip \
     zip \
     && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
WORKDIR /app

# ================================================================================

FROM base_python AS dev_python

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1
ENV RUNTIME=docker

COPY requirements-dev.txt .
RUN uv pip install -r requirements-dev.txt

# ================================================================================
# Built the GUI
# ================================================================================

FROM base_node AS dev_node

# Fetch and cache all (but only) the dependencies
COPY gui/yarn.lock gui/package.json gui/postinstall.js ./

RUN yarn --network-timeout 1200000

# Artifact for running the tests
COPY tests/states/archives/dft.json  /app/tests/states/archives/dft.json

# Copy and build the application itself
COPY gui .
RUN echo "REACT_APP_BACKEND_URL=/nomad-oasis" > .env

# ================================================================================

FROM dev_node AS build_node

RUN yarn run build

# ================================================================================
# Built the Python package
# ================================================================================

FROM dev_python AS dev_package

# Files required for artifact generation/testing
COPY ops/docker-compose ./ops/docker-compose

COPY nomad ./nomad
COPY scripts ./scripts
COPY .coveragerc \
     AUTHORS \
     LICENSE \
     MANIFEST.in \
     pyproject.toml \
     README.md \
     README.parsers.md \
     setup.py \
     ./

# for testing purposes
# todo: do we really need this to be bundled in the image?
COPY tests/data/parsers/archive.json ./tests/data/parsers/archive.json
COPY tests/data/examples/example.out ./tests/data/examples/example.out

# Build documentation with static version
RUN SETUPTOOLS_SCM_PRETEND_VERSION='0.0' uv pip install ".[parsing,infrastructure,dev]"

# Copy the built gui code
COPY --from=build_node /app/gui/build nomad/app/static/gui

# Set up the version as a build argument (default: '0.0')
ARG SETUPTOOLS_SCM_PRETEND_VERSION='0.0'

# Re-install project with correct version
RUN uv pip install ".[parsing,infrastructure,dev]"

# Build the python package.
RUN uv build

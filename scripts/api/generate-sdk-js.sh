#!/usr/bin/env bash
set -euo pipefail

openapi-generator-cli generate \
  -i docs/api/openapi.yaml \
  -g typescript-fetch \
  -o build/sdk-js

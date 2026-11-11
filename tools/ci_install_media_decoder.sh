#!/usr/bin/env bash
# CI-only original-media decoder; use pinned registry binaries if Ubuntu apt is unavailable.
set -euo pipefail

if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  ffprobe -version | sed -n '1p'
  exit 0
fi

if [[ "$RUNNER_OS" == "macOS" ]]; then
  brew install ffmpeg
else
  if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    echo "::error::DP419_CI_DECODER_UNSUPPORTED_RUNNER" >&2
    exit 1
  fi

  decoder_dir="$RUNNER_TEMP/dp419-ci-decoder"
  install_dir="$RUNNER_TEMP/dp419-ci-bin"
  # The exact published npm tarballs contain ELF binaries. Avoid install scripts.
  npm install --no-save --ignore-scripts --no-audit --no-fund \
    --prefix "$decoder_dir" \
    '@ffmpeg-installer/linux-x64@4.1.0' \
    '@ffprobe-installer/linux-x64@5.2.0'
  mkdir -p "$install_dir"
  install -m 755 "$decoder_dir/node_modules/@ffmpeg-installer/linux-x64/ffmpeg" "$install_dir/ffmpeg"
  install -m 755 "$decoder_dir/node_modules/@ffprobe-installer/linux-x64/ffprobe" "$install_dir/ffprobe"
  export PATH="$install_dir:$PATH"
  echo "$install_dir" >> "$GITHUB_PATH"
fi

command -v ffmpeg
command -v ffprobe
ffmpeg -version | sed -n '1p'
ffprobe -version | sed -n '1p'

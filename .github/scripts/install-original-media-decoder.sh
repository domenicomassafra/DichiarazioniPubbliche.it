#!/usr/bin/env bash
# CI-only DP-419 original-media decoder: immutable release asset and digest.
set -euo pipefail

asset="ffmpeg-n8.1.3-34-ga35157abb9-linux64-lgpl-8.1.tar.xz"
sha256="054c1d790fec22672a92b63fa12ee9e08483b59d84291df469b0d820a56163c5"
url="https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/autobuild-2026-11-10-12-39/${asset}"
archive="${RUNNER_TEMP}/${asset}"
bin_dir="${RUNNER_TEMP}/dp419-ffmpeg"

curl --fail --location --silent --show-error --retry 2 --max-time 120 \
  "${url}" --output "${archive}"
printf '%s  %s\n' "${sha256}" "${archive}" | sha256sum --check --status
mkdir -p "${bin_dir}"
tar -xJf "${archive}" -C "${bin_dir}" --strip-components=2 \
  --no-anchored ffmpeg ffprobe
chmod +x "${bin_dir}/ffmpeg" "${bin_dir}/ffprobe"
printf '%s\n' "${bin_dir}" >> "${GITHUB_PATH}"

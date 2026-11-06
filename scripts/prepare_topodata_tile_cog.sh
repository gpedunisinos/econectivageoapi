#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Uso: $0 entrada.vrt saida.tif [resolucao-em-graus]" >&2
  exit 1
fi

input="$1"
output="$2"
resolution="${3:-0.0008333333333333334}"
threads="${GDAL_NUM_THREADS:-ALL_CPUS}"

mkdir -p "$(dirname "$output")"
gdalwarp "$input" "$output" \
  -of COG \
  -te -75 -34 -34 6 \
  -tr "$resolution" "$resolution" \
  -tap \
  -r bilinear \
  -srcnodata -9999 \
  -dstnodata -9999 \
  -multi \
  -wo NUM_THREADS="$threads" \
  -co COMPRESS=DEFLATE \
  -co PREDICTOR=YES \
  -co BLOCKSIZE=512 \
  -co BIGTIFF=IF_SAFER \
  -co NUM_THREADS="$threads" \
  -co OVERVIEWS=AUTO \
  -co RESAMPLING=BILINEAR

metadata="$(gdalinfo "$output")"
grep -q "LAYOUT=COG" <<<"$metadata"
grep -q "Overviews:" <<<"$metadata"
sha256sum "$output" > "${output}.sha256"

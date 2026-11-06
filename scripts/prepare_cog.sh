#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Uso: $0 entrada.tif-ou-vrt saida.tif [nearest|bilinear]" >&2
  exit 1
fi

input="$1"
output="$2"
resampling="${3:-nearest}"

case "$resampling" in
  nearest|bilinear) ;;
  *)
    echo "Reamostragem inválida: $resampling" >&2
    exit 1
    ;;
esac

mkdir -p "$(dirname "$output")"
gdal_translate "$input" "$output" \
  -of COG \
  -co COMPRESS=DEFLATE \
  -co PREDICTOR=YES \
  -co BLOCKSIZE=512 \
  -co BIGTIFF=IF_SAFER \
  -co NUM_THREADS=ALL_CPUS \
  -co OVERVIEWS=AUTO \
  -co RESAMPLING="${resampling^^}"

metadata="$(gdalinfo "$output")"
grep -q "LAYOUT=COG" <<<"$metadata"
grep -q "Overviews:" <<<"$metadata"
sha256sum "$output" > "${output}.sha256"

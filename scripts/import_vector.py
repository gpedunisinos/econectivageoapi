#!/usr/bin/env python3
"""Importa e normaliza camadas vetoriais oficiais no PostGIS."""

import argparse
import subprocess
from pathlib import Path


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("biomes", "hydrography", "population"))
    parser.add_argument("source", type=Path)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--source-layer")
    args = parser.parse_args()

    table = {
        "biomes": "ibge_biomes_stage",
        "hydrography": "ana_hydrography_stage",
        "population": "ibge_census_sectors_stage",
    }[args.kind]
    command = [
        "ogr2ogr",
        "-f",
        "PostgreSQL",
        f"PG:{args.database_url}",
        str(args.source),
        "-nln",
        table,
        "-nlt",
        "PROMOTE_TO_MULTI",
        "-t_srs",
        "EPSG:4326",
        "-overwrite",
        "-lco",
        "GEOMETRY_NAME=geom",
    ]
    if args.source_layer:
        command.insert(6, args.source_layer)
    run(*command)
    print(f"Camada temporária {table} importada. Execute a normalização SQL documentada.")


if __name__ == "__main__":
    main()

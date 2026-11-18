"""Import a compressed Photon JSONL dump into a new local Photon database."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream a zstandard-compressed dump into Photon without extracting it."
    )
    parser.add_argument("--dump", type=Path, required=True, help="Path to the .jsonl.zst dump")
    parser.add_argument("--jar", type=Path, required=True, help="Path to photon-1.0.0.jar")
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="New, empty directory in which Photon will create photon_data",
    )
    args = parser.parse_args()

    dump_path = args.dump.resolve()
    jar_path = args.jar.resolve()
    data_dir = args.data_dir.resolve()
    if not dump_path.is_file():
        parser.error(f"Photon dump does not exist: {dump_path}")
    if not jar_path.is_file():
        parser.error(f"Photon JAR does not exist: {jar_path}")
    data_dir.mkdir(parents=True, exist_ok=True)
    if any(data_dir.iterdir()):
        parser.error(f"Photon data directory must be empty: {data_dir}")

    try:
        import zstandard
    except ImportError as exc:
        raise SystemExit(
            "Missing zstandard. Install the project's research extra with "
            "`python -m pip install -e \".[research]\"`."
        ) from exc

    command = [
        "java",
        "-jar",
        str(jar_path),
        "import",
        "-import-file",
        "-",
        "-country-codes",
        "KR",
    ]
    print(f"Importing South Korea Photon data into {data_dir}", flush=True)
    with dump_path.open("rb") as compressed:
        with zstandard.ZstdDecompressor().stream_reader(compressed) as dump_stream:
            process = subprocess.Popen(
                command,
                cwd=data_dir,
                stdin=subprocess.PIPE,
            )
            try:
                if process.stdin is None:
                    raise RuntimeError("Could not open Photon import input stream.")
                shutil.copyfileobj(dump_stream, process.stdin, length=1024 * 1024)
                process.stdin.close()
                return_code = process.wait()
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
                raise

    if return_code != 0:
        raise SystemExit(f"Photon import failed with exit code {return_code}.")
    print("Photon import completed successfully.", flush=True)


if __name__ == "__main__":
    main()

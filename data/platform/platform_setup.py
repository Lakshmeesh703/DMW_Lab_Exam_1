"""Run the part (a) platform setup from the repository root."""

from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
PLATFORM = ROOT / "data" / "platform"
DATABASE = PLATFORM / "annapurna.duckdb"


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    (ROOT / "data" / "object_store" / "manifest").mkdir(parents=True, exist_ok=True)
    try:
        urlopen("http://localhost:9000/minio/health/live", timeout=3).close()
    except OSError:
        run(["docker", "compose", "-f", str(PLATFORM / "minio-compose.yml"), "up", "-d"])
    run(["docker", "compose", "-f", str(PLATFORM / "docker-compose.yml"), "up", "-d"])
    run(["duckdb", str(DATABASE), "-init", str(PLATFORM / "land.sql")])
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PLATFORM / "upload_minio.ps1")])
    run(["duckdb", str(DATABASE), "-c", f".read {PLATFORM / 'query_demo.sql'}"])


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"Required command was not found: {error.filename}", file=sys.stderr)
        print("Install Docker Desktop and DuckDB, then run this script again.", file=sys.stderr)
        raise
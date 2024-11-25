import sys

import uvicorn

from tempapp.pipeline import get_temps


def main():
    if len(sys.argv) < 2:
        print("Usage: tempapp [run | get-temps | version]")
        sys.exit(1)

    command, *args = sys.argv[1:]
    dev = "dev" if "dev" in args else None

    command = sys.argv[1]
    if command == "run":
        uvicorn.run(
            "tempapp.app:app",
            host="0.0.0.0",
            port=8000,
            reload=True if dev == "dev" else False,
            reload_dirs=["src/tempapp"] if dev else None,
        )
    elif command == "get-temps":
        get_temps()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

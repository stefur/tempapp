import sys

import uvicorn

from tempapp.app import app  # type: ignore[import-untyped]
from tempapp.utils import get_temps  # type: ignore[import-untyped]


def main():
    if len(sys.argv) < 2:
        print("Usage: tempapp [run | get-temps]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "run":
        uvicorn.run(app, host="0.0.0.0", port=8000)
    elif command == "get-temps":
        get_temps()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

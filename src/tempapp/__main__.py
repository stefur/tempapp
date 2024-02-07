import uvicorn
from tempapp.app import app  # type: ignore


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

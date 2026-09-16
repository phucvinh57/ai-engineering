import uvicorn
from tauri_assistant.api.main import app


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)


if __name__ == "__main__":
    main()

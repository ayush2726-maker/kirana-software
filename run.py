import os
import uvicorn

# Registers advanced settings, reminders, users and injected settings assets.
import backend.settings_ext  # noqa: F401

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)

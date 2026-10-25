#!/usr/bin/env python
import os
import sys
import uvicorn

def main():
    print("=" * 60)
    print("      Starting AccessLearn AI Accessibility Platform")
    print("=" * 60)
    print("• Server URL: http://127.0.0.1:8000")
    print("• API Docs:   http://127.0.0.1:8000/docs")
    print("=" * 60)
    
    # reload=True watches the whole project tree for changes, including
    # storage/uploads, storage/outputs, and the local Whisper model cache --
    # every uploaded/generated file during processing looks like a source
    # change to it, which spawns extra reloader processes on Windows that
    # fight the transcription job for CPU. Off by default; set
    # ACCESSLEARN_DEV_RELOAD=1 when actively editing source code.
    reload_enabled = os.getenv("ACCESSLEARN_DEV_RELOAD", "").strip() == "1"
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        reload_dirs=["app", "static"] if reload_enabled else None,
    )

if __name__ == "__main__":
    main()

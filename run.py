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
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()

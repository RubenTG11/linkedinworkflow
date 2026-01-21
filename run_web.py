#!/usr/bin/env python3
"""Run the web frontend."""
import uvicorn

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  LinkedIn Posts Dashboard")
    print("  http://localhost:8000")
    print("=" * 50 + "\n")

    uvicorn.run(
        "src.web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

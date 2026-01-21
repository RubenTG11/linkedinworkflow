#!/usr/bin/env python3
"""
LinkedIn Post Creation System
Multi-Agent AI Workflow

Main entry point for the application.
"""
import asyncio
from loguru import logger

from src.tui.app import run_app


def setup_logging():
    """Configure logging - only to file, not console."""
    # Remove default handler that logs to console
    logger.remove()

    # Add file handler only
    logger.add(
        "logs/workflow_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    logger.info("Logging configured (file only)")


def main():
    """Main entry point."""
    # Setup logging
    setup_logging()

    logger.info("Starting LinkedIn Workflow System")

    # Run TUI application
    try:
        run_app()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.exception(f"Application error: {e}")
        raise
    finally:
        logger.info("Application shutdown")


if __name__ == "__main__":
    main()

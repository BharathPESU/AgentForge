"""Compatibility exports for synchronized Whiteboard operations."""

from backend.context.whiteboard import StaleWhiteboardUpdateError, Whiteboard

SynchronizedWhiteboard = Whiteboard

__all__ = ["StaleWhiteboardUpdateError", "SynchronizedWhiteboard", "Whiteboard"]

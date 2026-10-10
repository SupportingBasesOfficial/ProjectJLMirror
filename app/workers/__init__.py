"""Independent worker runtimes (ADR-001).

Workers run as separate processes from the API. Each worker has its own
event loop and interval. In production, each worker class may be deployed
and scaled independently.
"""

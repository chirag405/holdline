"""Holdline state package. Prefer `from holdline.state import store` and call
`store.create_task(...)` etc. -- the backend (DynamoDB or in-process) is chosen
by `STATE_BACKEND`."""

from holdline.state import store

__all__ = ["store"]

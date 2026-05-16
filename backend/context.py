# TEAMMATE 1 — owns this file
# Implement: get_context(channel_id), add_message(channel_id, role, content)
# See README for full spec.

_windows: dict[str, list[dict]] = {}
MAX_MESSAGES = 20


def get_context(channel_id: str) -> list[dict]:
    return _windows.get(channel_id, [])


def add_message(channel_id: str, role: str, content: str):
    if channel_id not in _windows:
        _windows[channel_id] = []
    _windows[channel_id].append({"role": role, "content": content})
    if len(_windows[channel_id]) > MAX_MESSAGES:
        _windows[channel_id] = _windows[channel_id][-MAX_MESSAGES:]

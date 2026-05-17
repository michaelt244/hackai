"""Regression test for the @penguin webhook chat-GUID filter.

The bug: inbound webhooks deliver 'iMessage;+;<id>' but the filter compared
against the send-side 'any;+;<id>' form -> never matched -> agent never ran.
"""
from penguin import _chat_id

# What BlueBubbles actually delivers in a webhook payload.
INBOUND = "iMessage;+;6d23dfa9618e444e81cc9220769d5c4d"
# What the send API / DEMO_CHAT_GUID uses.
SEND_FORM = "any;+;6d23dfa9618e444e81cc9220769d5c4d"
# A malformed env value with stray quotes (seen in .env).
MALFORMED = 'any;"+;6d23dfa9618e444e81cc9220769d5c4d"'

# The original bug: exact equality never matches a real webhook.
assert INBOUND != SEND_FORM, "precondition: the two forms differ literally"

# The fix: identifier-only comparison matches across service prefixes.
assert _chat_id(INBOUND) == _chat_id(SEND_FORM) == _chat_id(MALFORMED) == \
    "6d23dfa9618e444e81cc9220769d5c4d"

# The filter used in webhook(): demo id is a substring of the inbound guid.
demo_id = _chat_id(SEND_FORM)
assert demo_id in INBOUND.lower()
# A different chat must NOT match.
assert demo_id not in "iMessage;+;0000000000000000000000000000000".lower()

print("OK: chat-GUID filter regression test passed")

import os
import json
from anthropic import AsyncAnthropic
from context import get_augmented_system_prompt, add_message

anthropic = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are a relationship intelligence agent that parses voice notes about meetings and interactions.

INPUT: Raw voice transcription of a user talking about a meeting or contact.

OUTPUT: Respond ONLY with valid JSON, no other text:
{
  "contact": {
    "name": "string or null",
    "company": "string or null",
    "role": "string or null",
    "context": "string — what happened, any details"
  },
  "actionItems": ["array of specific next steps"],
  "sentiment": "positive | neutral | negative",
  "followUpDate": "ISO 8601 date string or null",
  "suggestedMessage": "1-2 sentence conversational summary of what to do next"
}"""


async def parse_voice_note(transcript: str, channel_id: str) -> dict:
    # Augment system prompt with this channel's memory
    augmented_prompt = await get_augmented_system_prompt(channel_id, SYSTEM_PROMPT)

    resp = await anthropic.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=augmented_prompt,
        messages=[{"role": "user", "content": transcript}],
    )

    result = json.loads(resp.content[0].text)

    # Save both sides to channel context for next call
    add_message(channel_id, "user", transcript)
    add_message(channel_id, "assistant", json.dumps(result))

    return result

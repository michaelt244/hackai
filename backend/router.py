import os
import re
from anthropic import AsyncAnthropic
from groq import AsyncGroq

anthropic = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
groq = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

# Cost per 1k output tokens in cents
MODEL_COSTS = {
    "groq/llama-3.1-8b-instant": 0.01,
    "claude-haiku-4-5-20251001": 0.08,
    "claude-sonnet-4-6": 0.25,
}

SIMPLE_PATTERNS = re.compile(
    r"\b(what is|who is|when is|how many|define|meaning of|capital of|"
    r"weather|time|date|hello|hi|hey|thanks|thank you|yes|no|ok)\b",
    re.IGNORECASE,
)

CODE_PATTERNS = re.compile(
    r"\b(code|function|debug|error|implement|algorithm|class|api|sql|"
    r"script|refactor|bug|exception|syntax)\b",
    re.IGNORECASE,
)


def _classify(message: str) -> str:
    if SIMPLE_PATTERNS.search(message):
        return "groq/llama-3.1-8b-instant"
    if CODE_PATTERNS.search(message) or len(message) > 300:
        return "claude-sonnet-4-6"
    return "claude-haiku-4-5-20251001"


async def _classify_with_groq(message: str) -> str:
    resp = await groq.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify this message into exactly one word: "
                    "simple, medium, or complex. "
                    "simple=facts/casual, medium=summaries/reasoning, complex=code/deep analysis"
                ),
            },
            {"role": "user", "content": message},
        ],
        max_tokens=5,
    )
    label = resp.choices[0].message.content.strip().lower()
    if label == "simple":
        return "groq/llama-3.1-8b-instant"
    if label == "complex":
        return "claude-sonnet-4-6"
    return "claude-haiku-4-5-20251001"


async def route_message(message: str, context: list[dict]) -> dict:
    model = _classify(message)

    # ambiguous — let Groq classify cheaply
    if model == "claude-haiku-4-5-20251001" and len(message) < 150:
        model = await _classify_with_groq(message)

    response = await _call_model(model, message, context)
    tokens_out = len(response.split()) * 1.3  # rough estimate
    cost = (tokens_out / 1000) * MODEL_COSTS[model]

    return {"response": response, "model": model, "cost": round(cost, 3)}


async def _call_model(model: str, message: str, context: list[dict]) -> str:
    messages = context + [{"role": "user", "content": message}]

    if model.startswith("groq/"):
        groq_model = model.split("/")[1]
        resp = await groq.chat.completions.create(
            model=groq_model,
            messages=messages,
            max_tokens=512,
        )
        return resp.choices[0].message.content

    resp = await anthropic.messages.create(
        model=model,
        max_tokens=1024,
        system="You are a helpful AI assistant in a group chat. Be concise and useful.",
        messages=messages,
    )
    return resp.content[0].text

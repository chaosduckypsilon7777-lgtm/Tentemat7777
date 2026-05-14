from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PROMPT = (
    "You are a financial and geopolitical analyst. In one concise sentence (max 25 words), "
    "explain why this signal matters to an investor or analyst. Be specific, not generic.\n\n"
    "Signal title: {title}\n"
    "Source: {source}\n"
    "Type: {signal_type}\n"
    "Score: {score}\n"
    "Reason: {reason}\n\n"
    "One sentence summary:"
)


def generate_summary(
    title: str | None,
    source_name: str,
    signal_type: str,
    score: float,
    reason: str,
    api_key: str,
) -> str | None:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT.format(
                        title=title or "—",
                        source=source_name,
                        signal_type=signal_type,
                        score=score,
                        reason=reason,
                    ),
                }
            ],
        )
        return message.content[0].text.strip()
    except ImportError:
        logger.warning("anthropic package not installed — skipping summary generation")
        return None
    except Exception as exc:
        logger.warning("summary generation failed: %s", exc)
        return None

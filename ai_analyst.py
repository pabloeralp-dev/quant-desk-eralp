"""Anthropic AI analyst — brief commentary and Q&A for QuantDesk."""

from __future__ import annotations

import os

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def get_commentary(context: dict, question: str = None) -> str:
    """Generate analyst commentary or answer a question about the model context.

    Args:
        context: Dict of model inputs/outputs (prices, Greeks, DCF results, etc.).
        question: Optional analyst question; if None, generates a 3-4 sentence brief.

    Returns:
        Analyst response as a string.
    """
    system = "You are a senior M&A analyst. Be concise, precise, professional. No disclaimers."
    prompt = f"Model context: {context}\n\n"
    prompt += f"Question: {question}" if question else "Write a 3-4 sentence analyst brief covering key risks."

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text

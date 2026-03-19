"""
Core agentic loop.

Supports text, images (JPEG/PNG/GIF/WEBP), and PDFs.
Uses the OpenAI-compatible Python SDK so the same code works with
GitHub Models, OpenAI, and Groq by swapping base_url + api_key.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maximum agentic iterations to prevent infinite loops
MAX_ITERATIONS = 10

SYSTEM_PROMPT = """You are EngiHub AI, a helpful assistant embedded in the EngiHub student toolkit.
You have access to tools that can read and modify the user's study notes, to-do list, expenses, \
and timetable. Always use the available tools when the user asks about their data.
When analysing uploaded files, summarise the key information clearly and offer to save relevant \
items (e.g., schedule entries, notes) to the database using your tools.
Be concise, friendly, and accurate."""


def _encode_image(image_bytes: bytes, mime_type: str) -> dict:
    """Build an OpenAI image_url content block from raw bytes."""
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    return {
        'type': 'image_url',
        'image_url': {'url': f'data:{mime_type};base64,{b64}', 'detail': 'auto'},
    }


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Return plain text extracted from a PDF byte stream."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ''
            pages.append(text)
        return '\n'.join(pages).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning('PDF extraction failed: %s', exc)
        return '[PDF text extraction failed]'


def _build_user_content(text: str, files: list[dict]) -> list[dict] | str:
    """
    Build the *content* value for the user message.

    *files* is a list of dicts: {'name': str, 'mime': str, 'data': bytes}
    Images are embedded as base64 data URLs; PDFs are converted to text blocks.
    Returns a list of content blocks if there are files, otherwise a plain string.
    """
    if not files:
        return text

    blocks: list[dict] = []
    if text:
        blocks.append({'type': 'text', 'text': text})

    for f in files:
        mime: str = f.get('mime', '')
        data: bytes = f.get('data', b'')
        name: str = f.get('name', 'file')

        if mime.startswith('image/'):
            blocks.append(_encode_image(data, mime))
        elif mime == 'application/pdf' or name.lower().endswith('.pdf'):
            extracted = _extract_pdf_text(data)
            blocks.append({
                'type': 'text',
                'text': f'[Contents of uploaded PDF "{name}"]\n{extracted}',
            })
        else:
            # Treat as plain text if possible
            try:
                decoded = data.decode('utf-8', errors='replace')
                blocks.append({
                    'type': 'text',
                    'text': f'[Contents of uploaded file "{name}"]\n{decoded}',
                })
            except Exception:  # noqa: BLE001
                blocks.append({'type': 'text', 'text': f'[Binary file "{name}" – cannot display]'})

    return blocks


def run_agent(
    user,
    prompt: str,
    files: list[dict] | None = None,
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Execute the full agentic loop and return a result dict:
        {
            'reply': str,             # Final assistant reply
            'tool_calls_made': list,  # Names of tools invoked
            'error': str | None,
        }

    *files* – list of {'name': str, 'mime': str, 'data': bytes}
    *conversation_history* – previous messages to keep context across turns
    """
    from django.contrib.auth.models import User as DjangoUser

    # -----------------------------------------------------------------------
    # Resolve API credentials
    # -----------------------------------------------------------------------
    try:
        api_key_cfg = user.api_key_config
    except Exception:  # noqa: BLE001
        return {
            'reply': '',
            'tool_calls_made': [],
            'error': (
                'No API key configured. Please visit AI Settings to add your '
                'GitHub Personal Access Token or another provider key.'
            ),
        }

    try:
        api_key = api_key_cfg.get_decrypted_api_key()
    except Exception as exc:  # noqa: BLE001
        logger.exception('Failed to decrypt API key for user %s', user.pk)
        return {'reply': '', 'tool_calls_made': [], 'error': f'Key decryption failed: {exc}'}

    base_url = api_key_cfg.get_base_url()
    model = api_key_cfg.preferred_model

    # -----------------------------------------------------------------------
    # Initialise OpenAI client (provider-agnostic via base_url)
    # -----------------------------------------------------------------------
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
    except Exception as exc:  # noqa: BLE001
        return {'reply': '', 'tool_calls_made': [], 'error': f'Failed to create client: {exc}'}

    # -----------------------------------------------------------------------
    # Import tools
    # -----------------------------------------------------------------------
    from .tool_registry import execute_tool, get_tool_schemas
    tool_schemas = get_tool_schemas()

    # -----------------------------------------------------------------------
    # Build initial message list
    # -----------------------------------------------------------------------
    messages: list[dict] = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)

    user_content = _build_user_content(prompt, files or [])
    messages.append({'role': 'user', 'content': user_content})

    # -----------------------------------------------------------------------
    # Agentic loop
    # -----------------------------------------------------------------------
    tools_invoked: list[str] = []

    for _iteration in range(MAX_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tool_schemas,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception('API call failed for user %s', user.pk)
            return {'reply': '', 'tool_calls_made': tools_invoked, 'error': str(exc)}

        choice = response.choices[0]
        assistant_message = choice.message

        # Append assistant turn to message list
        messages.append(assistant_message.model_dump(exclude_unset=True))

        # If no tool calls, the agent is done
        if not assistant_message.tool_calls:
            return {
                'reply': assistant_message.content or '',
                'tool_calls_made': tools_invoked,
                'error': None,
            }

        # Execute each tool call and feed results back
        for tc in assistant_message.tool_calls:
            fn_name = tc.function.name
            tools_invoked.append(fn_name)
            try:
                arguments = json.loads(tc.function.arguments or '{}')
            except json.JSONDecodeError:
                arguments = {}

            tool_result = execute_tool(fn_name, user, arguments)

            messages.append({
                'role': 'tool',
                'tool_call_id': tc.id,
                'content': tool_result,
            })

    # Exceeded max iterations
    return {
        'reply': 'I reached the maximum number of steps. Please try a simpler request.',
        'tool_calls_made': tools_invoked,
        'error': None,
    }

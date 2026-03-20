"""
Dynamic tool registry for the AI agent.

Each tool exposes:
  - schema : dict  – OpenAI-compatible function description (used in tool_choice)
  - handler: callable(user, **kwargs) -> dict  – executes the action and returns a result

The registry is a plain dict keyed by tool name so new tools can be added
just by appending to TOOLS and calling register_tools().
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.models import User
from django.utils import timezone

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _decimal_to_float(obj):
    """JSON-serialise Decimal values."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serialisable')


# ---------------------------------------------------------------------------
# Individual tool handlers
# ---------------------------------------------------------------------------

def _get_dashboard_summary(user: User, **_) -> dict:
    """Return a brief statistics overview for the authenticated user."""
    from tools.models import StudyNote, TodoItem, Expense, TimetableEntry
    from django.db.models import Sum

    notes = StudyNote.objects.filter(user=user).count()
    open_todos = TodoItem.objects.filter(user=user, completed=False).count()
    done_todos = TodoItem.objects.filter(user=user, completed=True).count()
    total_expenses = (
        Expense.objects.filter(user=user).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    )
    upcoming_events = TimetableEntry.objects.filter(user=user).count()
    return {
        'study_notes': notes,
        'open_todos': open_todos,
        'completed_todos': done_todos,
        'total_expenses': float(total_expenses),
        'timetable_entries': upcoming_events,
    }


def _get_study_notes(user: User, subject: str = '', **_) -> dict:
    from tools.models import StudyNote
    qs = StudyNote.objects.filter(user=user)
    if subject:
        qs = qs.filter(subject__icontains=subject)
    notes = [
        {'id': n.id, 'title': n.title, 'subject': n.subject,
         'content': n.content, 'updated_at': n.updated_at.isoformat()}
        for n in qs[:20]
    ]
    return {'notes': notes, 'count': len(notes)}


def _create_study_note(user: User, title: str, subject: str, content: str, **_) -> dict:
    from tools.models import StudyNote
    note = StudyNote.objects.create(user=user, title=title, subject=subject, content=content)
    return {'created': True, 'id': note.id, 'title': note.title}


def _get_todos(user: User, show_completed: bool = False, **_) -> dict:
    from tools.models import TodoItem
    qs = TodoItem.objects.filter(user=user)
    if not show_completed:
        qs = qs.filter(completed=False)
    todos = [
        {'id': t.id, 'title': t.title, 'priority': t.priority,
         'due_date': t.due_date.isoformat() if t.due_date else None,
         'completed': t.completed}
        for t in qs[:20]
    ]
    return {'todos': todos, 'count': len(todos)}


def _create_todo(user: User, title: str, description: str = '',
                 priority: str = 'medium', due_date: str | None = None, **_) -> dict:
    from tools.models import TodoItem
    import datetime
    parsed_date = None
    if due_date:
        try:
            parsed_date = datetime.date.fromisoformat(due_date)
        except ValueError:
            pass
    todo = TodoItem.objects.create(
        user=user, title=title, description=description,
        priority=priority, due_date=parsed_date,
    )
    return {'created': True, 'id': todo.id, 'title': todo.title}


def _get_expenses(user: User, category: str = '', **_) -> dict:
    from tools.models import Expense
    from django.db.models import Sum
    qs = Expense.objects.filter(user=user)
    if category:
        qs = qs.filter(category=category)
    total = qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')
    expenses = [
        {'id': e.id, 'title': e.title, 'amount': float(e.amount),
         'category': e.category, 'date': e.date.isoformat(), 'note': e.note}
        for e in qs[:20]
    ]
    return {'expenses': expenses, 'total': float(total), 'count': len(expenses)}


def _create_expense(user: User, title: str, amount: str,
                    category: str = 'other', date: str | None = None, note: str = '', **_) -> dict:
    from tools.models import Expense
    import datetime
    try:
        decimal_amount = Decimal(str(amount))
    except InvalidOperation:
        return {'error': f'Invalid amount: {amount}'}
    expense_date = datetime.date.today()
    if date:
        try:
            expense_date = datetime.date.fromisoformat(date)
        except ValueError:
            pass
    expense = Expense.objects.create(
        user=user, title=title, amount=decimal_amount,
        category=category, date=expense_date, note=note,
    )
    return {'created': True, 'id': expense.id, 'title': expense.title, 'amount': float(expense.amount)}


def _get_timetable(user: User, day_of_week: int | None = None, **_) -> dict:
    from tools.models import TimetableEntry
    DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    qs = TimetableEntry.objects.filter(user=user)
    if day_of_week is not None:
        qs = qs.filter(is_weekly=True, day_of_week=int(day_of_week))
    entries = [
        {
            'id': e.id, 'title': e.title, 'event_type': e.event_type,
            'location': e.location,
            'day': DAYS[e.day_of_week] if e.is_weekly and e.day_of_week is not None else None,
            'specific_date': e.specific_date.isoformat() if e.specific_date else None,
            'start_time': e.start_time.strftime('%H:%M'),
            'end_time': e.end_time.strftime('%H:%M'),
            'is_weekly': e.is_weekly,
        }
        for e in qs[:30]
    ]
    return {'entries': entries, 'count': len(entries)}


def _neuro_symbolic_parse(user: User, sentence: str, **_) -> dict:
    """
    Parse a natural language sentence using the neuro-symbolic engine.
    Returns the tokenised, classified, and connection graph as a dict.
    """
    from ai_agent.neuro_symbolic import evaluate_sentence
    return evaluate_sentence(sentence)


def _neuro_symbolic_query(user: User, word: str, **_) -> dict:
    """
    Look up a word in the built-in neuro-symbolic knowledge base and return
    all matching UniItems (operators, assignments, pronouns, etc.).
    """
    from ai_agent.neuro_symbolic import query_word
    matches = query_word(word)
    return {'word': word, 'matches': matches, 'count': len(matches)}


def _create_timetable_entry(
    user: User, title: str, event_type: str = 'lecture',
    location: str = '', start_time: str = '08:00', end_time: str = '09:00',
    is_weekly: bool = True, day_of_week: int | None = None,
    specific_date: str | None = None, color: str = '#1a73e8', **_
) -> dict:
    from tools.models import TimetableEntry
    import datetime
    parsed_start = datetime.time.fromisoformat(start_time)
    parsed_end = datetime.time.fromisoformat(end_time)
    parsed_date = None
    if specific_date:
        try:
            parsed_date = datetime.date.fromisoformat(specific_date)
        except ValueError:
            pass
    entry = TimetableEntry.objects.create(
        user=user, title=title, event_type=event_type, location=location,
        start_time=parsed_start, end_time=parsed_end,
        is_weekly=is_weekly,
        day_of_week=day_of_week if is_weekly else None,
        specific_date=parsed_date if not is_weekly else None,
        color=color,
    )
    return {'created': True, 'id': entry.id, 'title': entry.title}


# ---------------------------------------------------------------------------
# Tool definitions (schema + handler)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'get_dashboard_summary',
                'description': 'Return a summary of the user\'s data: note count, open todos, total expenses, and timetable entries.',
                'parameters': {'type': 'object', 'properties': {}, 'required': []},
            },
        },
        'handler': _get_dashboard_summary,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'get_study_notes',
                'description': 'List the user\'s study notes. Optionally filter by subject keyword.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'subject': {'type': 'string', 'description': 'Subject keyword filter (optional)'},
                    },
                    'required': [],
                },
            },
        },
        'handler': _get_study_notes,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'create_study_note',
                'description': 'Create a new study note for the user.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string', 'description': 'Title of the note'},
                        'subject': {'type': 'string', 'description': 'Subject or topic'},
                        'content': {'type': 'string', 'description': 'Body/content of the note'},
                    },
                    'required': ['title', 'subject', 'content'],
                },
            },
        },
        'handler': _create_study_note,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'get_todos',
                'description': 'List the user\'s to-do items.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'show_completed': {
                            'type': 'boolean',
                            'description': 'Include completed tasks (default false)',
                        },
                    },
                    'required': [],
                },
            },
        },
        'handler': _get_todos,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'create_todo',
                'description': 'Create a new to-do task for the user.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'description': {'type': 'string', 'description': 'Optional longer description'},
                        'priority': {'type': 'string', 'enum': ['low', 'medium', 'high'], 'description': 'Priority level'},
                        'due_date': {'type': 'string', 'description': 'ISO date string YYYY-MM-DD (optional)'},
                    },
                    'required': ['title'],
                },
            },
        },
        'handler': _create_todo,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'get_expenses',
                'description': 'List the user\'s recorded expenses. Optionally filter by category.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'category': {
                            'type': 'string',
                            'enum': ['food', 'transport', 'education', 'entertainment', 'utilities', 'other', ''],
                            'description': 'Category filter (empty = all)',
                        },
                    },
                    'required': [],
                },
            },
        },
        'handler': _get_expenses,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'create_expense',
                'description': 'Record a new expense for the user.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'amount': {'type': 'string', 'description': 'Decimal amount (e.g. "12.50")'},
                        'category': {
                            'type': 'string',
                            'enum': ['food', 'transport', 'education', 'entertainment', 'utilities', 'other'],
                        },
                        'date': {'type': 'string', 'description': 'ISO date YYYY-MM-DD (optional, defaults to today)'},
                        'note': {'type': 'string', 'description': 'Optional note'},
                    },
                    'required': ['title', 'amount'],
                },
            },
        },
        'handler': _create_expense,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'get_timetable',
                'description': 'Get the user\'s timetable entries. Optionally filter by day of week (0=Monday … 6=Sunday).',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'day_of_week': {
                            'type': 'integer',
                            'description': 'Day of week 0–6 (optional)',
                        },
                    },
                    'required': [],
                },
            },
        },
        'handler': _get_timetable,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'create_timetable_entry',
                'description': 'Add a new entry to the user\'s timetable.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'event_type': {
                            'type': 'string',
                            'enum': ['lecture', 'lab', 'tutorial', 'exam', 'meeting', 'other'],
                        },
                        'location': {'type': 'string', 'description': 'Room / place (optional)'},
                        'start_time': {'type': 'string', 'description': 'HH:MM'},
                        'end_time': {'type': 'string', 'description': 'HH:MM'},
                        'is_weekly': {'type': 'boolean', 'description': 'True for recurring weekly, false for one-time'},
                        'day_of_week': {'type': 'integer', 'description': '0=Monday … 6=Sunday (required if is_weekly=true)'},
                        'specific_date': {'type': 'string', 'description': 'ISO date YYYY-MM-DD (required if is_weekly=false)'},
                        'color': {'type': 'string', 'description': 'Hex colour code (optional)'},
                    },
                    'required': ['title', 'start_time', 'end_time'],
                },
            },
        },
        'handler': _create_timetable_entry,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'neuro_symbolic_parse',
                'description': (
                    'Parse a natural language sentence using the built-in '
                    'neuro-symbolic AI engine. Returns a symbolic breakdown: '
                    'tokens, their classifications (operator / assignment / '
                    'pronoun / object), connection graph, and evaluated results '
                    'for any operators or assignments found in the sentence. '
                    'Use this to reason about or explain a sentence symbolically.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'sentence': {
                            'type': 'string',
                            'description': 'The natural language sentence to parse.',
                        },
                    },
                    'required': ['sentence'],
                },
            },
        },
        'handler': _neuro_symbolic_parse,
    },
    {
        'schema': {
            'type': 'function',
            'function': {
                'name': 'neuro_symbolic_query',
                'description': (
                    'Query the neuro-symbolic knowledge base for a specific word. '
                    'Returns all built-in UniItems registered under that word '
                    '(e.g. operators like "and", "or", assignments like "is", "has", '
                    'pronouns like "it", "they"). Useful for introspecting what the '
                    'engine knows about a particular token.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'word': {
                            'type': 'string',
                            'description': 'The word to look up in the knowledge base.',
                        },
                    },
                    'required': ['word'],
                },
            },
        },
        'handler': _neuro_symbolic_query,
    },
]

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

# Keyed by function name for O(1) lookup during tool-call dispatch
_REGISTRY: dict[str, dict[str, Any]] = {}


def build_registry() -> None:
    """Populate _REGISTRY from the TOOLS list."""
    for tool in TOOLS:
        name = tool['schema']['function']['name']
        _REGISTRY[name] = tool


def get_tool_schemas() -> list[dict]:
    """Return the list of OpenAI-compatible tool schemas."""
    if not _REGISTRY:
        build_registry()
    return [t['schema'] for t in _REGISTRY.values()]


def execute_tool(name: str, user: User, arguments: dict) -> str:
    """
    Execute *name* with *arguments* in the context of *user*.
    Returns a JSON string that can be fed back to the model.
    """
    if not _REGISTRY:
        build_registry()
    tool = _REGISTRY.get(name)
    if tool is None:
        return json.dumps({'error': f'Unknown tool: {name}'})
    try:
        result = tool['handler'](user=user, **arguments)
        return json.dumps(result, default=_decimal_to_float)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({'error': str(exc)})


# Build on import
build_registry()

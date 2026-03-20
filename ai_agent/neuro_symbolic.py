"""
Neuro-Symbolic AI module for EngiHub.

Provides a symbolic language understanding engine with:
- Core data structures (UniObject, UniOperator, UniPronoun, UniAssignment,
  UniConnection, UniAction, UniSyntax, UniBase).
- Built-in operators with logic (AND, OR, NOT, IF, +, -, *, /, ==, >, <, …).
- Built-in assignments with logic (is, =, has, contains, belongs, …).
- Built-in pronouns with logic (it, this, that, he, she, they, …).
- A language phraser (parse_sentence / evaluate_sentence) that converts natural
  language sentences into a symbolic UniConnection graph.
"""

from __future__ import annotations

import re
from array import array
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id_array() -> array:
    return array("B")


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class UniTypes(IntEnum):
    UNIOBJECT     = 0
    UNIOPERATOR   = 1
    UNIPRONOUN    = 2
    UNIASSIGNMENT = 3
    UNICONNECTION = 4
    UNIACTION     = 5
    UNISYNTAX     = 6


class ArgsEnding(IntEnum):
    FIXED           = 0
    BY_END_OPERATOR = 1


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class UniObject:
    word: str = ""
    connections: list = field(default_factory=list)
    reverse_connections: array = field(default_factory=_new_id_array)
    type: int = UniTypes.UNIOBJECT
    logic: Callable = None
    memory: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class UniOperator:
    word: str = ""
    args_count: int = -1
    args_end: int = ArgsEnding.FIXED
    type: int = UniTypes.UNIOPERATOR
    logic: Callable = None
    memory: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class UniPronoun:
    word: object = None
    pointer: UniObject = None
    type: int = UniTypes.UNIPRONOUN
    logic: Callable = None
    memory: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class UniAssignment:
    word: object = None
    type: int = UniTypes.UNIASSIGNMENT
    logic: Callable = None
    memory: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class UniConnection:
    word: str = ""
    type: int = UniTypes.UNICONNECTION
    uniitem: UniOperator = None
    items: list = field(default_factory=list)
    memory: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class UniAction:
    word: object = None
    type: int = UniTypes.UNIACTION
    logic: Callable = None
    memory: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class UniSyntax:
    word: object = None
    type: int = UniTypes.UNISYNTAX
    logic: Callable = None
    memory: dict = field(default_factory=dict)


UniItem = UniObject | UniOperator | UniPronoun | UniAssignment | UniConnection | UniAction | UniSyntax


# ---------------------------------------------------------------------------
# UniBase – knowledge store
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class UniBase:
    items: dict = field(default_factory=dict)
    connections: list = field(default_factory=list)

    def add_item(self, item: UniItem) -> None:
        key = str(item.word).lower()
        if key not in self.items:
            self.items[key] = (item,)
        else:
            self.items[key] += (item,)

    def get_item(self, word: str) -> tuple:
        return self.items.get(word.lower(), ())

    def filter(self, word: str, connection):
        for item in self.items[word.lower()]:
            if connection in item.connections:
                yield item


# ---------------------------------------------------------------------------
# Built-in operator logic functions
# ---------------------------------------------------------------------------

def _logic_and(args: list) -> bool:
    return all(bool(a) for a in args)


def _logic_or(args: list) -> bool:
    return any(bool(a) for a in args)


def _logic_not(args: list) -> bool:
    return not bool(args[0]) if args else True


def _logic_if(args: list) -> object:
    if len(args) >= 2:
        return args[1] if bool(args[0]) else None
    return None


def _logic_equals(args: list) -> bool:
    if len(args) < 2:
        return False
    return args[0] == args[1]


def _logic_not_equals(args: list) -> bool:
    if len(args) < 2:
        return False
    return args[0] != args[1]


def _logic_greater(args: list) -> bool:
    if len(args) < 2:
        return False
    try:
        return float(args[0]) > float(args[1])
    except (TypeError, ValueError):
        return str(args[0]) > str(args[1])


def _logic_less(args: list) -> bool:
    if len(args) < 2:
        return False
    try:
        return float(args[0]) < float(args[1])
    except (TypeError, ValueError):
        return str(args[0]) < str(args[1])


def _logic_greater_eq(args: list) -> bool:
    if len(args) < 2:
        return False
    try:
        return float(args[0]) >= float(args[1])
    except (TypeError, ValueError):
        return str(args[0]) >= str(args[1])


def _logic_less_eq(args: list) -> bool:
    if len(args) < 2:
        return False
    try:
        return float(args[0]) <= float(args[1])
    except (TypeError, ValueError):
        return str(args[0]) <= str(args[1])


def _logic_add(args: list):
    try:
        return sum(float(a) for a in args)
    except (TypeError, ValueError):
        return "".join(str(a) for a in args)


def _logic_subtract(args: list):
    if not args:
        return 0
    try:
        result = float(args[0])
        for a in args[1:]:
            result -= float(a)
        return result
    except (TypeError, ValueError):
        return args[0]


def _logic_multiply(args: list):
    try:
        result = 1.0
        for a in args:
            result *= float(a)
        return result
    except (TypeError, ValueError):
        return args[0] if args else None


def _logic_divide(args: list):
    if len(args) < 2:
        return None
    try:
        divisor = float(args[1])
        if divisor == 0:
            return None
        return float(args[0]) / divisor
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Built-in assignment logic functions
# ---------------------------------------------------------------------------

def _logic_assign(args: list) -> dict:
    if len(args) < 2:
        return {}
    return {str(args[0]): args[1]}


def _logic_has(args: list) -> bool:
    if len(args) < 2:
        return False
    try:
        return args[1] in args[0]
    except TypeError:
        return False


def _logic_contains(args: list) -> bool:
    return _logic_has(args)


def _logic_belongs(args: list) -> bool:
    if len(args) < 2:
        return False
    try:
        return args[0] in args[1]
    except TypeError:
        return False


# ---------------------------------------------------------------------------
# Built-in pronoun logic functions
# ---------------------------------------------------------------------------

def _logic_pronoun_it(context: dict) -> object:
    return context.get("last_object")


def _logic_pronoun_this(context: dict) -> object:
    return context.get("current_object")


def _logic_pronoun_that(context: dict) -> object:
    return context.get("previous_object")


def _logic_pronoun_subject(context: dict) -> object:
    return context.get("subject")


# ---------------------------------------------------------------------------
# Global UniBase – populated with built-in items
# ---------------------------------------------------------------------------

_GLOBAL_BASE: UniBase = UniBase()


def _build_builtin_base() -> None:
    """Populate _GLOBAL_BASE with built-in operators, assignments, and pronouns."""

    # -- Operators -----------------------------------------------------------
    operators = [
        UniOperator(word="and",      args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_and),
        UniOperator(word="or",       args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_or),
        UniOperator(word="not",      args_count=1, args_end=ArgsEnding.FIXED,           logic=_logic_not),
        UniOperator(word="if",       args_count=2, args_end=ArgsEnding.BY_END_OPERATOR, logic=_logic_if),
        UniOperator(word="then",     args_count=0, args_end=ArgsEnding.FIXED,           logic=None),
        UniOperator(word="equals",   args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_equals),
        UniOperator(word="==",       args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_equals),
        UniOperator(word="!=",       args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_not_equals),
        UniOperator(word=">",        args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_greater),
        UniOperator(word="<",        args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_less),
        UniOperator(word=">=",       args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_greater_eq),
        UniOperator(word="<=",       args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_less_eq),
        UniOperator(word="+",        args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_add),
        UniOperator(word="-",        args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_subtract),
        UniOperator(word="*",        args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_multiply),
        UniOperator(word="/",        args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_divide),
        UniOperator(word="add",      args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_add),
        UniOperator(word="subtract", args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_subtract),
        UniOperator(word="multiply", args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_multiply),
        UniOperator(word="divide",   args_count=2, args_end=ArgsEnding.FIXED,           logic=_logic_divide),
    ]

    # -- Assignments ---------------------------------------------------------
    assignments = [
        UniAssignment(word="is",       logic=_logic_assign),
        UniAssignment(word="are",      logic=_logic_assign),
        UniAssignment(word="=",        logic=_logic_assign),
        UniAssignment(word="has",      logic=_logic_has),
        UniAssignment(word="have",     logic=_logic_has),
        UniAssignment(word="contains", logic=_logic_contains),
        UniAssignment(word="belong",   logic=_logic_belongs),
        UniAssignment(word="belongs",  logic=_logic_belongs),
    ]

    # -- Pronouns ------------------------------------------------------------
    pronouns = [
        UniPronoun(word="it",   logic=_logic_pronoun_it),
        UniPronoun(word="this", logic=_logic_pronoun_this),
        UniPronoun(word="that", logic=_logic_pronoun_that),
        UniPronoun(word="he",   logic=_logic_pronoun_subject),
        UniPronoun(word="she",  logic=_logic_pronoun_subject),
        UniPronoun(word="they", logic=_logic_pronoun_subject),
        UniPronoun(word="we",   logic=_logic_pronoun_subject),
        UniPronoun(word="i",    logic=_logic_pronoun_subject),
        UniPronoun(word="you",  logic=_logic_pronoun_subject),
    ]

    # -- Syntax markers ------------------------------------------------------
    syntax_items = [
        UniSyntax(word="("),
        UniSyntax(word=")"),
        UniSyntax(word=","),
        UniSyntax(word="."),
        UniSyntax(word="?"),
        UniSyntax(word="!"),
    ]

    for item in operators + assignments + pronouns + syntax_items:
        _GLOBAL_BASE.add_item(item)


_build_builtin_base()


# ---------------------------------------------------------------------------
# Language Phraser
# ---------------------------------------------------------------------------

_OBJECT_TYPES = frozenset({
    UniTypes.UNIOBJECT,
    UniTypes.UNIPRONOUN,
})

_OPERATOR_TYPES = frozenset({
    UniTypes.UNIOPERATOR,
    UniTypes.UNIASSIGNMENT,
})


def _tokenize(text: str) -> list[str]:
    """Split *text* on whitespace, preserving punctuation as separate tokens."""
    tokens = re.findall(r"[\w']+|[+\-*/=!<>(),.!?]", text)
    return [t.lower() for t in tokens]


def _classify_token(token: str, base: UniBase) -> UniItem:
    """
    Return the first matching UniItem for *token* from *base*.
    Falls back to a plain UniObject for unknown words.
    """
    if token in base.items:
        return base.items[token][0]
    return UniObject(word=token)


@dataclass
class ParseResult:
    """Holds the output of parsing a natural language sentence."""
    tokens: list
    classified: list       # list of {'token': str, 'type': str, 'item': UniItem}
    connections: list      # list of UniConnection
    context: dict


def parse_sentence(text: str, base: UniBase | None = None) -> ParseResult:
    """
    Parse a natural language sentence into a symbolic structure.

    Algorithm
    ---------
    1. Tokenize *text*.
    2. Classify each token (UNIOPERATOR / UNIASSIGNMENT / UNIPRONOUN /
       UNIOBJECT / UNISYNTAX).
    3. For each operator / assignment token, collect the nearest neighbouring
       object / pronoun tokens as arguments and emit a UniConnection.
    4. Return a ParseResult.
    """
    if base is None:
        base = _GLOBAL_BASE

    tokens = _tokenize(text)

    classified: list[dict] = []
    for tok in tokens:
        item = _classify_token(tok, base)
        classified.append({
            "token": tok,
            "type": UniTypes(item.type).name,
            "item": item,
        })

    connections: list[UniConnection] = []
    context: dict = {
        "last_object": None,
        "current_object": None,
        "previous_object": None,
        "subject": None,
    }

    for i, entry in enumerate(classified):
        item = entry["item"]
        if item.type not in _OPERATOR_TYPES:
            continue

        # Collect left-side objects/pronouns immediately preceding this token
        left_items: list[UniItem] = []
        j = i - 1
        while j >= 0 and classified[j]["item"].type in _OBJECT_TYPES:
            left_items.insert(0, classified[j]["item"])
            j -= 1

        # Collect right-side objects/pronouns immediately following this token
        right_items: list[UniItem] = []
        if isinstance(item, UniOperator) and item.args_count >= 0:
            needed = max(item.args_count - len(left_items), 0)
            k = i + 1
            while k < len(classified) and len(right_items) < max(needed, 1):
                if classified[k]["item"].type in _OBJECT_TYPES:
                    right_items.append(classified[k]["item"])
                k += 1
        else:
            k = i + 1
            while k < len(classified) and classified[k]["item"].type in _OBJECT_TYPES:
                right_items.append(classified[k]["item"])
                k += 1

        all_items = left_items + right_items
        conn = UniConnection(
            word=entry["token"],
            uniitem=item if isinstance(item, UniOperator) else None,
            items=all_items,
        )
        connections.append(conn)

        # Update context for pronoun resolution
        if all_items:
            context["previous_object"] = context.get("last_object")
            context["last_object"] = all_items[-1]
            if context["subject"] is None:
                context["subject"] = all_items[0]

    return ParseResult(
        tokens=tokens,
        classified=classified,
        connections=connections,
        context=context,
    )


def evaluate_sentence(text: str, base: UniBase | None = None) -> dict:
    """
    Parse *text* and evaluate every operator / assignment that has logic.

    Returns a plain dict suitable for JSON serialisation.
    """
    result = parse_sentence(text, base)

    evaluations: list[dict] = []
    for conn in result.connections:
        args = [item.word for item in conn.items]

        if conn.uniitem is not None and conn.uniitem.logic is not None:
            val = conn.uniitem.logic(args)
            evaluations.append({
                "operator": conn.word,
                "type": "UNIOPERATOR",
                "args": args,
                "result": val,
            })
        elif conn.uniitem is None:
            # Look up the assignment item from classified list
            for entry in result.classified:
                if (
                    entry["token"] == conn.word
                    and entry["item"].type == UniTypes.UNIASSIGNMENT
                    and entry["item"].logic is not None
                ):
                    val = entry["item"].logic(args)
                    evaluations.append({
                        "operator": conn.word,
                        "type": "UNIASSIGNMENT",
                        "args": args,
                        "result": val,
                    })
                    break

    return {
        "input": text,
        "tokens": result.tokens,
        "classified": [
            {"token": c["token"], "type": c["type"]}
            for c in result.classified
        ],
        "connections": [
            {"operator": c.word, "items": [i.word for i in c.items]}
            for c in result.connections
        ],
        "evaluations": evaluations,
    }


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def add_knowledge(word: str, item: UniItem, base: UniBase | None = None) -> None:
    """Register a custom UniItem in *base* (defaults to the global base)."""
    if base is None:
        base = _GLOBAL_BASE
    base.add_item(item)


def get_builtin_base() -> UniBase:
    """Return the global built-in UniBase instance."""
    return _GLOBAL_BASE


def query_word(word: str, base: UniBase | None = None) -> list[dict]:
    """
    Look up all UniItems registered under *word* in *base*.
    Returns a list of dicts with 'word', 'type', and 'args_count' (for operators).
    """
    if base is None:
        base = _GLOBAL_BASE
    key = word.lower()
    if key not in base.items:
        return []
    results = []
    for item in base.items[key]:
        entry = {"word": str(item.word), "type": UniTypes(item.type).name}
        if isinstance(item, UniOperator):
            entry["args_count"] = item.args_count
            entry["args_end"] = ArgsEnding(item.args_end).name
        results.append(entry)
    return results

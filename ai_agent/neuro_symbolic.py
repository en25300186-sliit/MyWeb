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
    UNIQUESTION   = 7


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
    question_logic: Callable = None
    memory: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class UniQuestion:
    """Represents a WH-question word (what, where, when, who, why, how, which).

    Has two logics:
    - question_logic: invoked when the word appears in an interrogative sentence.
    - conditional_logic: invoked when the word appears in a conditional/declarative
      sentence (e.g. "what you think matters").
    """
    word: object = None
    type: int = UniTypes.UNIQUESTION
    question_logic: Callable = None
    conditional_logic: Callable = None
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


UniItem = UniObject | UniOperator | UniPronoun | UniAssignment | UniConnection | UniAction | UniSyntax | UniQuestion


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
# Built-in question-logic functions  (used when words appear in questions)
# ---------------------------------------------------------------------------

def _logic_question_lookup(args: list) -> str:
    """Placeholder: actual fact lookup is handled by NeuroSymbolicSession."""
    return f"? ({' '.join(str(a) for a in args)})"


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
        UniAssignment(word="is",       logic=_logic_assign,    question_logic=_logic_question_lookup),
        UniAssignment(word="are",      logic=_logic_assign,    question_logic=_logic_question_lookup),
        UniAssignment(word="am",       logic=_logic_assign,    question_logic=_logic_question_lookup),
        UniAssignment(word="=",        logic=_logic_assign),
        UniAssignment(word="has",      logic=_logic_has,       question_logic=_logic_question_lookup),
        UniAssignment(word="have",     logic=_logic_has,       question_logic=_logic_question_lookup),
        UniAssignment(word="contains", logic=_logic_contains),
        UniAssignment(word="belong",   logic=_logic_belongs),
        UniAssignment(word="belongs",  logic=_logic_belongs),
    ]

    # -- Pronouns (personal + possessive) -----------------------------------
    pronouns = [
        UniPronoun(word="it",    logic=_logic_pronoun_it),
        UniPronoun(word="this",  logic=_logic_pronoun_this),
        UniPronoun(word="that",  logic=_logic_pronoun_that),
        UniPronoun(word="he",    logic=_logic_pronoun_subject),
        UniPronoun(word="she",   logic=_logic_pronoun_subject),
        UniPronoun(word="they",  logic=_logic_pronoun_subject),
        UniPronoun(word="we",    logic=_logic_pronoun_subject),
        UniPronoun(word="i",     logic=_logic_pronoun_subject),
        UniPronoun(word="you",   logic=_logic_pronoun_subject),
        # Possessive pronouns / determiners
        UniPronoun(word="my",    logic=_logic_pronoun_subject),
        UniPronoun(word="your",  logic=_logic_pronoun_subject),
        UniPronoun(word="his",   logic=_logic_pronoun_subject),
        UniPronoun(word="her",   logic=_logic_pronoun_subject),
        UniPronoun(word="its",   logic=_logic_pronoun_subject),
        UniPronoun(word="our",   logic=_logic_pronoun_subject),
        UniPronoun(word="their", logic=_logic_pronoun_subject),
    ]

    # -- WH-question words ---------------------------------------------------
    questions = [
        UniQuestion(word="what",  question_logic=_logic_question_lookup, conditional_logic=None),
        UniQuestion(word="where", question_logic=_logic_question_lookup, conditional_logic=None),
        UniQuestion(word="when",  question_logic=_logic_question_lookup, conditional_logic=None),
        UniQuestion(word="who",   question_logic=_logic_question_lookup, conditional_logic=None),
        UniQuestion(word="whom",  question_logic=_logic_question_lookup, conditional_logic=None),
        UniQuestion(word="why",   question_logic=_logic_question_lookup, conditional_logic=None),
        UniQuestion(word="how",   question_logic=_logic_question_lookup, conditional_logic=None),
        UniQuestion(word="which", question_logic=_logic_question_lookup, conditional_logic=None),
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

    for item in operators + assignments + pronouns + questions + syntax_items:
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
    UniTypes.UNIQUESTION,
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

    Pronouns are resolved against the parsing context before evaluation.
    Returns a plain dict suitable for JSON serialisation.
    """
    result = parse_sentence(text, base)
    context = result.context

    def _resolve_pronoun_or_get_word(item) -> str:
        """Resolve a UniPronoun to its referent word, or return the item's word."""
        if item.type == UniTypes.UNIPRONOUN and item.logic is not None:
            resolved = item.logic(context)
            if resolved is not None:
                return str(resolved.word) if hasattr(resolved, "word") else str(resolved)
        return str(item.word)

    evaluations: list[dict] = []
    for conn in result.connections:
        args = [_resolve_pronoun_or_get_word(item) for item in conn.items]

        if conn.uniitem is not None and conn.uniitem.logic is not None:
            val = conn.uniitem.logic(args)
            evaluations.append({
                "operator": conn.word,
                "type": "UNIOPERATOR",
                "args": args,
                "result": val,
            })
        elif conn.uniitem is None:
            # Look up the assignment/question item from classified list
            for entry in result.classified:
                if entry["token"] != conn.word:
                    continue
                if entry["item"].type == UniTypes.UNIASSIGNMENT and entry["item"].logic is not None:
                    val = entry["item"].logic(args)
                    evaluations.append({
                        "operator": conn.word,
                        "type": "UNIASSIGNMENT",
                        "args": args,
                        "result": val,
                    })
                    break
                if entry["item"].type == UniTypes.UNIQUESTION and entry["item"].question_logic is not None:
                    val = entry["item"].question_logic(args)
                    evaluations.append({
                        "operator": conn.word,
                        "type": "UNIQUESTION",
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
            {"operator": c.word, "items": [_resolve_pronoun_or_get_word(i) for i in c.items]}
            for c in result.connections
        ],
        "evaluations": evaluations,
    }


# ---------------------------------------------------------------------------
# Q&A engine – sentence-level helpers
# ---------------------------------------------------------------------------

# Words that are skipped when extracting subject/value tokens from a sentence.
_SKIP_WORDS: frozenset = frozenset({"the", "a", "an"})

# Assignment relation words (verbs that link subject to value).
_ASSIGNMENT_WORDS: frozenset = frozenset({"is", "are", "am", "=", "has", "have"})

# WH-question words recognised by the Q&A engine.
_QUESTION_WORDS: frozenset = frozenset({"what", "where", "when", "who", "whom", "why", "how", "which"})

# Possessive determiners: these precede a noun to indicate ownership.
# e.g. "my name", "your car", "his book"
_POSSESSIVE_WORDS: frozenset = frozenset({"my", "your", "his", "her", "its", "our", "their"})

# Flip table for first/second-person pronouns when constructing AI answers.
# e.g. user says "my name" → AI replies "your name"
_POSSESSIVE_FLIP: dict = {
    "my":    "your",
    "your":  "my",
    "our":   "your",
    "i":     "you",
    "me":    "you",
    "we":    "you",
    "you":   "I",
}


def _split_sentences(text: str) -> list[tuple[str, bool]]:
    """
    Split *text* into a list of ``(sentence, is_question)`` tuples.

    Sentences are delimited by ``.``, ``!``, or ``?``.  A sentence ending with
    ``?`` is marked as a question; all others are treated as declarative.
    """
    parts = re.split(r"(?<=[.!?])\s*", text.strip())
    result: list[tuple[str, bool]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        is_question = part.endswith("?")
        clean = part.rstrip(".!?").strip()
        if clean:
            result.append((clean, is_question))
    return result


def _extract_fact_from_tokens(tokens: list[str]) -> dict | None:
    """
    Extract a subject–relation–value fact from a list of *tokens*.

    Returns a dict ``{possessive, subject, relation, value}`` where
    ``possessive`` may be ``None``, or ``None`` if no fact pattern is found.
    """
    for i, tok in enumerate(tokens):
        if tok not in _ASSIGNMENT_WORDS:
            continue
        left = [t for t in tokens[:i] if t not in _SKIP_WORDS]
        right = [t for t in tokens[i + 1:] if t not in _SKIP_WORDS]
        if not left or not right:
            continue
        possessive = left[0] if left[0] in _POSSESSIVE_WORDS else None
        subject_parts = left[1:] if possessive else left
        subject = " ".join(subject_parts)
        value = " ".join(right)
        if subject:
            return {
                "possessive": possessive,
                "subject": subject,
                "relation": tok,
                "value": value,
            }
    return None


def _try_answer_question(tokens: list[str], facts: list[dict]) -> str | None:
    """
    Try to answer a question sentence (given as *tokens*) using *facts*.

    Returns a natural-language answer string, or ``None`` if no matching
    fact is found.
    """
    # Locate the WH-word
    q_word: str | None = None
    q_idx: int = -1
    for i, tok in enumerate(tokens):
        if tok in _QUESTION_WORDS:
            q_word = tok
            q_idx = i
            break

    if q_word is None:
        # Yes/no question fallback – not a WH question, skip
        return None

    # Locate the first assignment/relation word after the question word
    a_word: str | None = None
    a_idx: int = -1
    for i in range(q_idx + 1, len(tokens)):
        if tokens[i] in _ASSIGNMENT_WORDS:
            a_word = tokens[i]
            a_idx = i
            break

    if a_word is None:
        return None

    # Everything after the relation word is the subject being asked about
    subject_tokens = [t for t in tokens[a_idx + 1:] if t not in _SKIP_WORDS]
    if not subject_tokens:
        return None

    # Detect possessive at the start of subject tokens
    possessive: str | None = None
    if subject_tokens[0] in _POSSESSIVE_WORDS:
        possessive = subject_tokens[0]
        subject_tokens = subject_tokens[1:]

    subject = " ".join(subject_tokens)
    if not subject:
        return None

    # Search facts for a matching entry
    for fact in facts:
        fact_subject = fact.get("subject", "").lower()
        fact_relation = fact.get("relation", "").lower()
        fact_possessive = (fact.get("possessive") or "").lower()
        fact_value = fact.get("value", "")

        # Normalise relation: treat is/are/am as equivalent
        def _rel_match(r1: str, r2: str) -> bool:
            equiv = {"is", "are", "am"}
            if r1 == r2:
                return True
            return r1 in equiv and r2 in equiv

        if fact_subject != subject.lower():
            continue
        if not _rel_match(fact_relation, a_word):
            continue
        if fact_possessive != (possessive.lower() if possessive else ""):
            continue

        # Found a matching fact – construct the answer
        answer_relation = fact_relation
        if possessive and (answer_possessive := _POSSESSIVE_FLIP.get(possessive)):
            return f"{answer_possessive} {subject} {answer_relation} {fact_value}"
        return f"{subject} {answer_relation} {fact_value}"

    return None


def process_input(text: str, facts: list[dict] | None = None,
                  base: UniBase | None = None) -> dict:
    """
    Process a multi-sentence *text* string.

    For each declarative sentence, facts are extracted and appended to
    *facts*.  For each question sentence, the engine looks up an answer in
    the accumulated facts.

    Returns::

        {
            "input": str,
            "sentences": [{"text": str, "is_question": bool}, ...],
            "new_facts": [...],          # facts extracted in this call
            "answers": [...],            # answers for question sentences
            "reply": str,                # natural-language reply
        }
    """
    if facts is None:
        facts = []
    if base is None:
        base = _GLOBAL_BASE

    sentences = _split_sentences(text)
    new_facts: list[dict] = []
    answers: list[str] = []

    for sentence_text, is_question in sentences:
        tokens = _tokenize(sentence_text)
        if is_question:
            answer = _try_answer_question(tokens, facts)
            answers.append(answer if answer is not None else "I don't know.")
        else:
            fact = _extract_fact_from_tokens(tokens)
            if fact is not None:
                facts.append(fact)
                new_facts.append(fact)

    return {
        "input": text,
        "sentences": [{"text": s, "is_question": q} for s, q in sentences],
        "new_facts": new_facts,
        "answers": answers,
        "reply": " ".join(answers) if answers else "",
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
        if isinstance(item, UniAssignment):
            entry["has_question_logic"] = item.question_logic is not None
        if isinstance(item, UniQuestion):
            entry["has_question_logic"] = item.question_logic is not None
            entry["has_conditional_logic"] = item.conditional_logic is not None
        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Session-scoped neuro-symbolic engine
# ---------------------------------------------------------------------------

class NeuroSymbolicSession:
    """
    A per-session wrapper that combines the global built-in knowledge base
    with user-defined custom facts.

    Facts added to a session are serialisable (plain dicts) so they can be
    stored in Django's session framework and the engine reconstructed on
    each request.
    """

    def __init__(self) -> None:
        # Start with a shallow copy of the global base's items mapping
        self._base = UniBase()
        self._base.items = dict(_GLOBAL_BASE.items)
        self._facts: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, text: str) -> dict:
        """Parse and evaluate *text* using the session knowledge base."""
        return evaluate_sentence(text, self._base)

    def query(self, word: str) -> dict:
        """Query the session knowledge base for *word*."""
        matches = query_word(word, self._base)
        return {"word": word, "matches": matches, "count": len(matches)}

    def add_fact(self, subject: str, relation: str, value: str,
                 possessive: str | None = None) -> dict:
        """
        Add a subject–relation–value triple to the session knowledge base.

        The optional *possessive* parameter (e.g. ``"my"``) allows storing
        possessive facts such as "my name is geemeth".
        The subject and value tokens are registered as :class:`UniObject`
        entries so the parser can recognise them.
        """
        for token in (subject.lower(), value.lower()):
            if token not in self._base.items:
                self._base.add_item(UniObject(word=token))
        fact: dict = {
            "subject": subject,
            "relation": relation,
            "value": value,
            "possessive": possessive or "",
        }
        self._facts.append(fact)
        return {"added": True, **fact}

    def load_facts(self, facts: list[dict]) -> None:
        """Replay a serialised list of facts (e.g. from the Django session)."""
        for fact in facts:
            self.add_fact(
                fact["subject"],
                fact["relation"],
                fact["value"],
                possessive=fact.get("possessive"),
            )

    def answer_input(self, text: str) -> dict:
        """
        Process a multi-sentence *text* string using the session knowledge base.

        Declarative sentences are parsed for facts which are stored in the
        session.  Question sentences are answered using the accumulated facts.

        Returns a dict with keys ``input``, ``sentences``, ``new_facts``,
        ``answers``, and ``reply``.

        Example::

            session.answer_input("my name is geemeth. what is my name?")
            # → {"reply": "your name is geemeth", ...}
        """
        result = process_input(text, facts=self._facts, base=self._base)
        # Register newly extracted facts in the session base so the parser
        # recognises these words in future sentences.
        for fact in result["new_facts"]:
            subj = fact.get("subject", "")
            val = fact.get("value", "")
            for token in (subj.lower(), val.lower()):
                if token and token not in self._base.items:
                    self._base.add_item(UniObject(word=token))
        return result

    @property
    def facts(self) -> list[dict]:
        """Return a copy of the accumulated custom facts."""
        return list(self._facts)

    @property
    def custom_words(self) -> list[str]:
        """Return words present in the session base but not in the global base."""
        global_keys = set(_GLOBAL_BASE.items.keys())
        return [k for k in self._base.items if k not in global_keys]

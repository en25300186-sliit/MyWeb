import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .agent import run_agent
from .encryption import encrypt_value
from .forms import APIKeySettingsForm
from .models import PROVIDER_CONFIG, AgentConversation, AgentMessage, UserAPIKey


# ---------------------------------------------------------------------------
# API Key Settings
# ---------------------------------------------------------------------------

@login_required
def api_key_settings(request):
    """Allow the user to configure (or update) their AI provider key."""
    instance = UserAPIKey.objects.filter(user=request.user).first()
    has_key = instance is not None

    if request.method == 'POST':
        form = APIKeySettingsForm(request.POST, instance=instance)
        if form.is_valid():
            key_obj = form.save(commit=False)
            key_obj.user = request.user
            raw_key = form.cleaned_data['api_key']
            key_obj.encrypted_api_key = encrypt_value(raw_key)
            key_obj.save()
            messages.success(request, 'API key saved and encrypted successfully!')
            return redirect('ai_chat')
    else:
        form = APIKeySettingsForm(instance=instance)

    # Build provider → default model map and provider → models list for JS auto-fill
    provider_defaults = {k: v['default_model'] for k, v in PROVIDER_CONFIG.items()}
    provider_models = {k: v.get('models', []) for k, v in PROVIDER_CONFIG.items()}

    return render(request, 'ai_agent/settings.html', {
        'form': form,
        'has_key': has_key,
        'provider_defaults': json.dumps(provider_defaults),
        'provider_models': json.dumps(provider_models),
    })


# ---------------------------------------------------------------------------
# Chat page
# ---------------------------------------------------------------------------

@login_required
def chat_page(request):
    """Render the chat UI."""
    has_api_key = UserAPIKey.objects.filter(user=request.user).exists()
    # Load or create a conversation for this session
    session_key = 'ai_agent_session_id'
    session_id = request.session.get(session_key)
    conversation = None
    if session_id:
        conversation = AgentConversation.objects.filter(
            user=request.user, session_id=session_id
        ).first()
    if not conversation:
        conversation = AgentConversation.objects.create(user=request.user)
        request.session[session_key] = str(conversation.session_id)

    history = list(conversation.messages.values('role', 'content', 'tool_name', 'created_at'))
    return render(request, 'ai_agent/chat.html', {
        'has_api_key': has_api_key,
        'conversation': conversation,
        'history': history,
    })


@login_required
def new_conversation(request):
    """Start a fresh conversation (clear session pointer)."""
    if 'ai_agent_session_id' in request.session:
        del request.session['ai_agent_session_id']
    return redirect('ai_chat')


# ---------------------------------------------------------------------------
# AJAX send endpoint
# ---------------------------------------------------------------------------

@login_required
@require_POST
def chat_send(request):
    """
    Accept a user message (+ optional file uploads) and return the agent reply.
    Expected POST fields:
        message  – text prompt
        session_id (optional) – UUID of existing conversation
    Optional FILES:
        files[]  – one or more files (images / PDFs)
    Returns JSON:
        { reply, tool_calls_made, error, session_id }
    """
    text = request.POST.get('message', '').strip()
    session_id_str = request.POST.get('session_id', '')

    if not text and not request.FILES:
        return JsonResponse({'error': 'Empty message.'}, status=400)

    # Resolve or create conversation
    conversation = None
    if session_id_str:
        try:
            conversation = AgentConversation.objects.filter(
                user=request.user, session_id=uuid.UUID(session_id_str)
            ).first()
        except ValueError:
            pass
    if not conversation:
        conversation = AgentConversation.objects.create(user=request.user)
        request.session['ai_agent_session_id'] = str(conversation.session_id)

    # Build file list for the agent
    files = []
    for uploaded in request.FILES.getlist('files[]'):
        files.append({
            'name': uploaded.name,
            'mime': uploaded.content_type or 'application/octet-stream',
            'data': uploaded.read(),
        })

    # Build condensed conversation history (last 20 turns to limit token usage)
    history_msgs = list(
        conversation.messages.order_by('-created_at')[:20]
    )[::-1]
    history = []
    for msg in history_msgs:
        if msg.role in ('user', 'assistant'):
            history.append({'role': msg.role, 'content': msg.content})

    # Persist the user message
    AgentMessage.objects.create(
        conversation=conversation,
        role='user',
        content=text,
    )

    # Run the agentic loop
    result = run_agent(
        user=request.user,
        prompt=text,
        files=files,
        conversation_history=history,
    )

    # Persist the assistant reply
    if result.get('reply'):
        AgentMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=result['reply'],
        )

    # Persist tool call summaries
    for tool_name in result.get('tool_calls_made', []):
        AgentMessage.objects.create(
            conversation=conversation,
            role='tool',
            content=f'Tool executed: {tool_name}',
            tool_name=tool_name,
        )

    return JsonResponse({
        'reply': result.get('reply', ''),
        'tool_calls_made': result.get('tool_calls_made', []),
        'error': result.get('error'),
        'session_id': str(conversation.session_id),
    })


# ---------------------------------------------------------------------------
# Neuro-Symbolic AI interface
# ---------------------------------------------------------------------------

_NS_SESSION_KEY = 'neuro_symbolic_facts'


def _rebuild_session(request):
    """
    Reconstruct a :class:`NeuroSymbolicSession` from the stored fact list in
    the Django session.  Returns the session engine and the raw facts list.
    """
    from .neuro_symbolic import NeuroSymbolicSession
    facts = request.session.get(_NS_SESSION_KEY, [])
    engine = NeuroSymbolicSession()
    engine.load_facts(facts)
    return engine, facts


@login_required
def neuro_symbolic_view(request):
    """Render the Neuro-Symbolic AI interactive interface."""
    _engine, facts = _rebuild_session(request)
    return render(request, 'ai_agent/neuro_symbolic.html', {'facts': facts})


@login_required
@require_POST
def neuro_symbolic_process(request):
    """
    AJAX endpoint for the Neuro-Symbolic AI interface.

    Expected request body: JSON with key ``action`` plus action-specific keys.

    Actions
    -------
    parse    – ``{"action": "parse", "sentence": "<text>"}``
    query    – ``{"action": "query", "word": "<word>"}``
    add_fact – ``{"action": "add_fact", "subject": "...", "relation": "...", "value": "..."}``
    clear    – ``{"action": "clear"}``

    Returns JSON ``{"ok": true, "result": {...}}`` or ``{"error": "..."}``
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    action = body.get('action', '')
    engine, facts = _rebuild_session(request)

    if action == 'parse':
        sentence = body.get('sentence', '').strip()
        if not sentence:
            return JsonResponse({'error': 'No sentence provided.'}, status=400)
        result = engine.parse(sentence)
        return JsonResponse({'ok': True, 'result': result})

    elif action == 'query':
        word = body.get('word', '').strip()
        if not word:
            return JsonResponse({'error': 'No word provided.'}, status=400)
        result = engine.query(word)
        return JsonResponse({'ok': True, 'result': result})

    elif action == 'add_fact':
        subject = body.get('subject', '').strip()
        relation = body.get('relation', '').strip()
        value = body.get('value', '').strip()
        if not subject or not relation or not value:
            return JsonResponse(
                {'error': 'subject, relation, and value are all required.'}, status=400
            )
        engine.add_fact(subject, relation, value)
        facts.append({'subject': subject, 'relation': relation, 'value': value})
        request.session[_NS_SESSION_KEY] = facts
        request.session.modified = True
        return JsonResponse({'ok': True, 'facts': facts})

    elif action == 'clear':
        request.session[_NS_SESSION_KEY] = []
        request.session.modified = True
        return JsonResponse({'ok': True, 'facts': []})

    else:
        return JsonResponse({'error': f'Unknown action: {action!r}'}, status=400)

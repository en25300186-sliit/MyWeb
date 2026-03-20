from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from decimal import Decimal
from .models import StudyNote, TodoItem, Expense, TimetableEntry
from .forms import StudyNoteForm, TodoForm, ExpenseForm, TimetableEntryForm
import json
import datetime
import os
import platform
import queue
import threading
import time


# ---------------------------------------------------------------------------
# AI Studio – Browser Manager
# ---------------------------------------------------------------------------

class BrowserManager:
    """Thread-safe singleton that drives a persistent Playwright browser window
    pointed at Google AI Studio (headless=False so the user can see the browser
    and sign in if necessary)."""

    _instance = None
    _class_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton factory
    # ------------------------------------------------------------------

    @classmethod
    def get(cls):
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self):
        self._page = None
        self._context = None
        self._thread = None
        self._status = 'stopped'   # stopped | launching | running | error
        self._error = None
        self._cmd_q = queue.Queue()
        self._res_q = queue.Queue()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def status(self):
        return self._status

    @property
    def is_running(self):
        return self._status == 'running'

    # ------------------------------------------------------------------
    # Public API (called from Django request threads)
    # ------------------------------------------------------------------

    def launch(self):
        """Start the browser thread (non-blocking).  Returns immediately."""
        if self._status in ('launching', 'running'):
            return {'success': True, 'message': f'Browser already {self._status}'}
        self._status = 'launching'
        self._error = None
        self._thread = threading.Thread(target=self._browser_thread, daemon=True)
        self._thread.start()
        return {'success': True, 'message': 'Browser launch initiated'}

    def stop(self):
        """Ask the browser thread to shut down."""
        if self._status not in ('running', 'launching'):
            return {'success': False, 'message': f'Browser is not active (status: {self._status})'}
        self._cmd_q.put(('__stop__', {}))
        return {'success': True, 'message': 'Stop signal sent'}

    def switch_model(self, model_name):
        return self._send_cmd('switch_model', model=model_name)

    def set_system_instruction(self, instruction):
        return self._send_cmd('set_system_instruction', instruction=instruction)

    def new_chat(self):
        return self._send_cmd('new_chat')

    def list_chats(self):
        return self._send_cmd('list_chats')

    def delete_chat(self, title):
        return self._send_cmd('delete_chat', title=title)

    def send_message(self, message):
        return self._send_cmd('send_message', message=message)

    def navigate_to(self, url):
        return self._send_cmd('navigate', url=url)

    def add_tool(self, tool_name):
        return self._send_cmd('add_tool', tool_name=tool_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_cmd(self, cmd, **kwargs):
        if not self.is_running:
            return {'success': False, 'error': 'Browser is not running'}
        self._cmd_q.put((cmd, kwargs))
        try:
            return self._res_q.get(timeout=30)
        except queue.Empty:
            return {'success': False, 'error': 'Command timed out after 30 s'}

    @staticmethod
    def _chrome_profile_dir():
        system = platform.system()
        if system == 'Windows':
            local_app = os.environ.get('LOCALAPPDATA', '')
            return os.path.join(local_app, 'Google', 'Chrome', 'User Data')
        if system == 'Darwin':
            return os.path.expanduser('~/Library/Application Support/Google/Chrome')
        # Linux default
        return os.path.expanduser('~/.config/google-chrome')

    # ------------------------------------------------------------------
    # Browser thread
    # ------------------------------------------------------------------

    def _browser_thread(self):
        try:
            from playwright.sync_api import sync_playwright  # imported here to avoid import-time errors
            with sync_playwright() as pw:
                profile_dir = self._chrome_profile_dir()
                try:
                    self._context = pw.chromium.launch_persistent_context(
                        user_data_dir=profile_dir,
                        headless=False,
                        channel='chrome',
                        args=['--no-first-run', '--disable-blink-features=AutomationControlled'],
                    )
                except Exception as primary_exc:
                    import logging as _logging
                    _logging.getLogger(__name__).warning(
                        'Could not launch Chrome with default profile (%s). '
                        'Falling back to dedicated AI Studio profile.',
                        primary_exc,
                    )
                    # Fallback: dedicated profile so Chrome isn't locked by an open instance
                    self._context = pw.chromium.launch_persistent_context(
                        user_data_dir=os.path.join(os.path.expanduser('~'), '.aistudio_profile'),
                        headless=False,
                        args=['--no-first-run'],
                    )

                pages = self._context.pages
                self._page = pages[0] if pages else self._context.new_page()
                self._page.goto('https://aistudio.google.com/prompts/new_chat',
                                wait_until='domcontentloaded')
                self._status = 'running'

                # Command loop
                while True:
                    try:
                        cmd, kwargs = self._cmd_q.get(timeout=0.5)
                    except queue.Empty:
                        # Check whether the browser window was closed by the user
                        try:
                            _ = self._context.pages
                        except Exception:
                            break
                        continue

                    if cmd == '__stop__':
                        break

                    result = self._dispatch(cmd, kwargs)
                    self._res_q.put(result)

        except Exception as exc:
            self._error = str(exc)
            self._status = 'error'
        finally:
            self._status = 'stopped'
            try:
                if self._context:
                    self._context.close()
            except Exception:
                pass
            self._context = None
            self._page = None

    # ------------------------------------------------------------------
    # Command dispatch (runs inside the browser thread)
    # ------------------------------------------------------------------

    def _dispatch(self, cmd, kwargs):
        try:
            handler = {
                'switch_model': self._do_switch_model,
                'set_system_instruction': self._do_set_system_instruction,
                'new_chat': self._do_new_chat,
                'list_chats': self._do_list_chats,
                'delete_chat': self._do_delete_chat,
                'send_message': self._do_send_message,
                'navigate': self._do_navigate,
                'add_tool': self._do_add_tool,
            }.get(cmd)
            if handler is None:
                return {'success': False, 'error': f'Unknown command: {cmd}'}
            return handler(**kwargs)
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    # --- individual command handlers ---

    def _do_switch_model(self, model):
        page = self._page
        # The model selector button varies; try a few selectors
        selectors = [
            '[data-test-id="model-selector"]',
            'ms-model-selector button',
            'button[aria-label*="model" i]',
            'button[aria-label*="Model" i]',
        ]
        clicked = False
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=3000)
                page.click(sel)
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            return {'success': False, 'error': 'Model selector not found – please select manually in the browser.'}

        page.wait_for_timeout(800)
        # Find list item matching model name
        opts = page.query_selector_all('[role="option"], mat-option, .model-option')
        for opt in opts:
            try:
                text = (opt.inner_text() or '').strip()
                if model.lower() in text.lower():
                    opt.click()
                    return {'success': True, 'message': f'Model switched to "{text}"'}
            except Exception:
                continue
        return {'success': False, 'error': f'Model "{model}" not found in list.'}

    def _do_set_system_instruction(self, instruction):
        page = self._page
        selectors = [
            'textarea[aria-label*="system" i]',
            'textarea[placeholder*="system" i]',
            '[data-test-id="system-instructions-input"] textarea',
            'ms-system-instructions textarea',
        ]
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=3000)
                page.fill(sel, instruction)
                return {'success': True, 'message': 'System instruction set.'}
            except Exception:
                continue
        return {'success': False, 'error': 'System instruction field not found. Try expanding it in the browser first.'}

    def _do_new_chat(self):
        page = self._page
        page.goto('https://aistudio.google.com/prompts/new_chat', wait_until='domcontentloaded')
        page.wait_for_timeout(1500)
        return {'success': True, 'message': 'New chat opened.'}

    def _do_list_chats(self):
        page = self._page
        page.goto('https://aistudio.google.com/library', wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        selectors = [
            '.prompt-item',
            'ms-prompt-list-item',
            '[data-test-id="prompt-item"]',
            '.ms-project-card',
        ]
        chats = []
        for sel in selectors:
            items = page.query_selector_all(sel)
            if items:
                for item in items[:30]:
                    title_el = (
                        item.query_selector('.title')
                        or item.query_selector('h3')
                        or item.query_selector('h4')
                        or item.query_selector('[class*="title"]')
                    )
                    title = (title_el.inner_text() if title_el else item.inner_text() or 'Untitled').strip()
                    chats.append({'title': title})
                break
        return {'success': True, 'chats': chats}

    def _do_delete_chat(self, title):
        page = self._page
        page.goto('https://aistudio.google.com/library', wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        # Find the matching card and look for a delete / more-options button
        selectors = ['.prompt-item', 'ms-prompt-list-item', '[data-test-id="prompt-item"]', '.ms-project-card']
        for sel in selectors:
            items = page.query_selector_all(sel)
            for item in items:
                title_el = (
                    item.query_selector('.title')
                    or item.query_selector('h3')
                    or item.query_selector('h4')
                )
                item_title = (title_el.inner_text() if title_el else '').strip()
                if title.lower() in item_title.lower():
                    # Hover to reveal context menu
                    item.hover()
                    page.wait_for_timeout(400)
                    btn = (
                        item.query_selector('button[aria-label*="delete" i]')
                        or item.query_selector('button[aria-label*="more" i]')
                        or item.query_selector('[mat-icon-button]')
                    )
                    if btn:
                        btn.click()
                        page.wait_for_timeout(500)
                        # Locale-independent: prefer ARIA/data attributes; fall back to text
                        confirm = (
                            page.query_selector('[aria-label*="delete" i]')
                            or page.query_selector('[data-test-id*="delete" i]')
                            or page.query_selector('button:has-text("Delete")')
                            or page.query_selector('button:has-text("Confirm")')
                            or page.query_selector('button:has-text("OK")')
                            or page.query_selector('[role="button"]:has-text("Delete")')
                        )
                        if confirm:
                            confirm.click()
                        return {'success': True, 'message': f'Deleted "{item_title}".'}
                    return {'success': False, 'error': 'Delete button not found for that chat.'}
        return {'success': False, 'error': f'Chat "{title}" not found.'}

    def _do_send_message(self, message):
        page = self._page
        selectors = [
            'textarea[placeholder*="Type" i]',
            'textarea[aria-label*="prompt" i]',
            '[data-test-id="prompt-input"] textarea',
            'ms-prompt-input textarea',
            '.prompt-textarea',
        ]
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=3000)
                page.fill(sel, message)
                # Try pressing Enter first; if it doesn't trigger submission, click the send button
                page.keyboard.press('Enter')
                page.wait_for_timeout(800)
                # Check whether a send/submit button is present and still enabled as a fallback
                send_btn = (
                    page.query_selector('button[aria-label*="send" i]')
                    or page.query_selector('button[aria-label*="run" i]')
                    or page.query_selector('[data-test-id="send-button"]')
                )
                if send_btn and send_btn.is_enabled():
                    send_btn.click()
                return {'success': True, 'message': 'Message sent.'}
            except Exception:
                continue
        return {'success': False, 'error': 'Message input not found on the current page.'}

    def _do_navigate(self, url):
        self._page.goto(url, wait_until='domcontentloaded')
        return {'success': True, 'message': f'Navigated to {url}'}

    def _do_add_tool(self, tool_name):
        page = self._page
        selectors = [
            'button[aria-label*="tool" i]',
            'button:has-text("Add tool")',
            '[data-test-id="add-tool"]',
        ]
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=3000)
                page.click(sel)
                page.wait_for_timeout(600)
                opt = page.query_selector(f'[role="option"]:has-text("{tool_name}")')
                if opt:
                    opt.click()
                    return {'success': True, 'message': f'Tool "{tool_name}" added.'}
            except Exception:
                continue
        return {'success': False, 'error': 'Could not add tool automatically – please add it manually in the browser.'}


# ---------------------------------------------------------------------------
# AI Studio – Django views
# ---------------------------------------------------------------------------

_AISTUDIO_MODELS = [
    'Gemini 2.5 Pro',
    'Gemini 2.0 Flash',
    'Gemini 2.0 Flash-Lite',
    'Gemini 1.5 Pro',
    'Gemini 1.5 Flash',
    'Gemini 1.5 Flash-8B',
]


@login_required
def aistudio_launcher(request):
    """Render the AI Studio control-panel page."""
    mgr = BrowserManager.get()
    return render(request, 'tools/aistudio_launcher.html', {
        'browser_status': mgr.status,
        'is_running': mgr.is_running,
        'models': _AISTUDIO_MODELS,
    })


@login_required
def aistudio_launch(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    result = BrowserManager.get().launch()
    return JsonResponse(result)


@login_required
def aistudio_stop(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    result = BrowserManager.get().stop()
    return JsonResponse(result)


@login_required
def aistudio_status(request):
    mgr = BrowserManager.get()
    return JsonResponse({'status': mgr.status, 'is_running': mgr.is_running})


@login_required
def aistudio_action(request):
    """Generic AJAX endpoint for all browser actions."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    action = data.get('action', '')
    mgr = BrowserManager.get()

    dispatch = {
        'switch_model': lambda: mgr.switch_model(data.get('model', '')),
        'set_system_instruction': lambda: mgr.set_system_instruction(data.get('instruction', '')),
        'new_chat': lambda: mgr.new_chat(),
        'list_chats': lambda: mgr.list_chats(),
        'delete_chat': lambda: mgr.delete_chat(data.get('title', '')),
        'send_message': lambda: mgr.send_message(data.get('message', '')),
        'navigate': lambda: mgr.navigate_to(data.get('url', 'https://aistudio.google.com/prompts/new_chat')),
        'add_tool': lambda: mgr.add_tool(data.get('tool_name', '')),
    }

    handler = dispatch.get(action)
    if handler is None:
        return JsonResponse({'success': False, 'error': f'Unknown action: {action}'})
    return JsonResponse(handler())


def server_time(request):
    """JSON endpoint returning current server time (no login required for live clock)."""
    now = timezone.localtime(timezone.now())
    return JsonResponse({
        'time': now.strftime('%H:%M:%S'),
        'date': now.strftime('%A, %d %B %Y'),
        'iso': now.isoformat(),
    })


@login_required
def api_today_timetable(request):
    """JSON API returning today's timetable entries for notifications."""
    today = timezone.localdate()
    weekday = today.weekday()  # 0=Monday ... 6=Sunday

    weekly = TimetableEntry.objects.filter(user=request.user, is_weekly=True, day_of_week=weekday)
    specific = TimetableEntry.objects.filter(user=request.user, is_weekly=False, specific_date=today)
    entries = list(weekly) + list(specific)
    entries.sort(key=lambda e: e.start_time)

    data = [
        {
            'id': e.id,
            'title': e.title,
            'event_type': e.event_type,
            'location': e.location,
            'start_time': e.start_time.strftime('%H:%M'),
            'end_time': e.end_time.strftime('%H:%M'),
            'color': e.color,
        }
        for e in entries
    ]
    return JsonResponse({'entries': data})


@login_required
def dashboard(request):
    notes_count = StudyNote.objects.filter(user=request.user).count()
    todos_count = TodoItem.objects.filter(user=request.user, completed=False).count()
    total_expenses = Expense.objects.filter(user=request.user).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    today = timezone.localdate()
    weekday = today.weekday()
    weekly_today = TimetableEntry.objects.filter(user=request.user, is_weekly=True, day_of_week=weekday)
    specific_today = TimetableEntry.objects.filter(user=request.user, is_weekly=False, specific_date=today)
    today_entries = sorted(list(weekly_today) + list(specific_today), key=lambda e: e.start_time)

    context = {
        'notes_count': notes_count,
        'todos_count': todos_count,
        'total_expenses': total_expenses,
        'today_entries': today_entries,
        'today_name': today.strftime('%A, %d %B %Y'),
    }
    return render(request, 'tools/dashboard.html', context)


@login_required
def unit_converter(request):
    result = None
    if request.method == 'POST':
        try:
            value = float(request.POST.get('value', 0))
            from_unit = request.POST.get('from_unit')
            to_unit = request.POST.get('to_unit')
            category = request.POST.get('category')

            conversions = {
                'length': {
                    'mm': 0.001, 'cm': 0.01, 'm': 1.0, 'km': 1000.0,
                    'inch': 0.0254, 'foot': 0.3048, 'yard': 0.9144, 'mile': 1609.344,
                },
                'mass': {
                    'mg': 0.000001, 'g': 0.001, 'kg': 1.0, 'tonne': 1000.0,
                    'oz': 0.0283495, 'lb': 0.453592, 'ton': 907.185,
                },
                'temperature': {
                    'celsius': 'celsius', 'fahrenheit': 'fahrenheit', 'kelvin': 'kelvin',
                },
                'area': {
                    'mm2': 1e-6, 'cm2': 1e-4, 'm2': 1.0, 'km2': 1e6,
                    'ft2': 0.092903, 'acre': 4046.86, 'hectare': 10000.0,
                },
                'volume': {
                    'ml': 0.001, 'l': 1.0, 'm3': 1000.0,
                    'fl_oz': 0.0295735, 'cup': 0.236588, 'pint': 0.473176, 'gallon': 3.78541,
                },
                'speed': {
                    'm_s': 1.0, 'km_h': 0.277778, 'mph': 0.44704, 'knot': 0.514444,
                },
                'pressure': {
                    'pa': 1.0, 'kpa': 1000.0, 'mpa': 1e6, 'bar': 1e5,
                    'psi': 6894.76, 'atm': 101325.0,
                },
                'energy': {
                    'j': 1.0, 'kj': 1000.0, 'mj': 1e6, 'cal': 4.184, 'kcal': 4184.0,
                    'kwh': 3.6e6, 'btu': 1055.06,
                },
            }

            if category == 'temperature':
                if from_unit == 'celsius':
                    if to_unit == 'fahrenheit':
                        result = value * 9 / 5 + 32
                    elif to_unit == 'kelvin':
                        result = value + 273.15
                    else:
                        result = value
                elif from_unit == 'fahrenheit':
                    if to_unit == 'celsius':
                        result = (value - 32) * 5 / 9
                    elif to_unit == 'kelvin':
                        result = (value - 32) * 5 / 9 + 273.15
                    else:
                        result = value
                elif from_unit == 'kelvin':
                    if to_unit == 'celsius':
                        result = value - 273.15
                    elif to_unit == 'fahrenheit':
                        result = (value - 273.15) * 9 / 5 + 32
                    else:
                        result = value
            elif category in conversions:
                conv = conversions[category]
                if from_unit in conv and to_unit in conv:
                    result = value * conv[from_unit] / conv[to_unit]
        except (ValueError, ZeroDivisionError):
            messages.error(request, 'Invalid input values.')

    return render(request, 'tools/unit_converter.html', {'result': result})


@login_required
def gpa_calculator(request):
    return render(request, 'tools/gpa_calculator.html')


@login_required
def resistor_calculator(request):
    return render(request, 'tools/resistor_calculator.html')


@login_required
def study_timer(request):
    return render(request, 'tools/study_timer.html')


@login_required
def study_notes(request):
    notes = StudyNote.objects.filter(user=request.user)
    return render(request, 'tools/study_notes.html', {'notes': notes})


@login_required
def note_create(request):
    if request.method == 'POST':
        form = StudyNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, 'Note created successfully!')
            return redirect('study_notes')
    else:
        form = StudyNoteForm()
    return render(request, 'tools/note_form.html', {'form': form, 'action': 'Create'})


@login_required
def note_edit(request, pk):
    note = get_object_or_404(StudyNote, pk=pk, user=request.user)
    if request.method == 'POST':
        form = StudyNoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, 'Note updated successfully!')
            return redirect('study_notes')
    else:
        form = StudyNoteForm(instance=note)
    return render(request, 'tools/note_form.html', {'form': form, 'action': 'Edit'})


@login_required
def note_delete(request, pk):
    note = get_object_or_404(StudyNote, pk=pk, user=request.user)
    if request.method == 'POST':
        note.delete()
        messages.success(request, 'Note deleted.')
    return redirect('study_notes')


@login_required
def todo_list(request):
    todos = TodoItem.objects.filter(user=request.user)
    form = TodoForm()
    if request.method == 'POST':
        form = TodoForm(request.POST)
        if form.is_valid():
            todo = form.save(commit=False)
            todo.user = request.user
            todo.save()
            messages.success(request, 'Task added!')
            return redirect('todo_list')
    return render(request, 'tools/todo_list.html', {'todos': todos, 'form': form})


@login_required
def todo_toggle(request, pk):
    todo = get_object_or_404(TodoItem, pk=pk, user=request.user)
    todo.completed = not todo.completed
    todo.save()
    return redirect('todo_list')


@login_required
def todo_delete(request, pk):
    todo = get_object_or_404(TodoItem, pk=pk, user=request.user)
    todo.delete()
    messages.success(request, 'Task deleted.')
    return redirect('todo_list')


@login_required
def budget_tracker(request):
    expenses = Expense.objects.filter(user=request.user)
    form = ExpenseForm()
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, 'Expense recorded!')
            return redirect('budget_tracker')

    total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    by_category = {}
    for cat_code, cat_name in Expense.CATEGORY_CHOICES:
        cat_total = expenses.filter(category=cat_code).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        if cat_total > 0:
            by_category[cat_name] = float(cat_total)

    context = {
        'expenses': expenses,
        'form': form,
        'total': total,
        'by_category_json': json.dumps(by_category),
    }
    return render(request, 'tools/budget_tracker.html', context)


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    expense.delete()
    messages.success(request, 'Expense deleted.')
    return redirect('budget_tracker')


@login_required
def timetable(request):
    DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    today = timezone.localdate()
    weekday = today.weekday()

    # Build weekly grid
    weekly_entries = TimetableEntry.objects.filter(user=request.user, is_weekly=True)
    weekly_by_day = {i: [] for i in range(7)}
    for entry in weekly_entries:
        if entry.day_of_week is not None:
            weekly_by_day[entry.day_of_week].append(entry)

    # Upcoming specific-date events (today and future)
    upcoming = TimetableEntry.objects.filter(
        user=request.user, is_weekly=False, specific_date__gte=today
    ).order_by('specific_date', 'start_time')

    context = {
        'days': list(enumerate(DAYS)),
        'weekly_by_day': weekly_by_day,
        'upcoming': upcoming,
        'today_weekday': weekday,
    }
    return render(request, 'tools/timetable.html', context)


@login_required
def timetable_create(request):
    if request.method == 'POST':
        form = TimetableEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            messages.success(request, 'Timetable entry added!')
            return redirect('timetable')
    else:
        form = TimetableEntryForm()
    return render(request, 'tools/timetable_form.html', {'form': form, 'action': 'Add'})


@login_required
def timetable_edit(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TimetableEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, 'Entry updated!')
            return redirect('timetable')
    else:
        form = TimetableEntryForm(instance=entry)
    return render(request, 'tools/timetable_form.html', {'form': form, 'action': 'Edit'})


@login_required
def timetable_delete(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Entry deleted.')
    return redirect('timetable')

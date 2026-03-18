from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from decimal import Decimal
from .models import StudyNote, TodoItem, Expense
from .forms import StudyNoteForm, TodoForm, ExpenseForm
import json


@login_required
def dashboard(request):
    notes_count = StudyNote.objects.filter(user=request.user).count()
    todos_count = TodoItem.objects.filter(user=request.user, completed=False).count()
    total_expenses = Expense.objects.filter(user=request.user).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    context = {
        'notes_count': notes_count,
        'todos_count': todos_count,
        'total_expenses': total_expenses,
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

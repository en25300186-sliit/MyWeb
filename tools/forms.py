from django import forms
from .models import StudyNote, TodoItem, Expense, TimetableEntry


class StudyNoteForm(forms.ModelForm):
    class Meta:
        model = StudyNote
        fields = ['title', 'subject', 'content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 8}),
        }


class TodoForm(forms.ModelForm):
    class Meta:
        model = TodoItem
        fields = ['title', 'description', 'priority', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'amount', 'category', 'date', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = [
            'title', 'event_type', 'location', 'description', 'color',
            'is_weekly', 'day_of_week', 'specific_date',
            'start_time', 'end_time',
        ]
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'specific_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

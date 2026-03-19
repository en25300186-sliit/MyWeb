from django.contrib import admin
from .models import StudyNote, TodoItem, Expense, TimetableEntry


@admin.register(StudyNote)
class StudyNoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'user', 'updated_at']
    list_filter = ['subject', 'user']
    search_fields = ['title', 'content']


@admin.register(TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'priority', 'due_date', 'completed']
    list_filter = ['priority', 'completed', 'user']
    search_fields = ['title']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'amount', 'category', 'date', 'user']
    list_filter = ['category', 'user', 'date']
    search_fields = ['title']


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'user', 'is_weekly', 'day_of_week', 'specific_date', 'start_time', 'end_time']
    list_filter = ['event_type', 'is_weekly', 'user']
    search_fields = ['title', 'location']

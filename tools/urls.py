from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('tools/unit-converter/', views.unit_converter, name='unit_converter'),
    path('tools/gpa-calculator/', views.gpa_calculator, name='gpa_calculator'),
    path('tools/resistor-calculator/', views.resistor_calculator, name='resistor_calculator'),
    path('tools/study-timer/', views.study_timer, name='study_timer'),
    path('tools/study-notes/', views.study_notes, name='study_notes'),
    path('tools/study-notes/create/', views.note_create, name='note_create'),
    path('tools/study-notes/<int:pk>/edit/', views.note_edit, name='note_edit'),
    path('tools/study-notes/<int:pk>/delete/', views.note_delete, name='note_delete'),
    path('tools/todo/', views.todo_list, name='todo_list'),
    path('tools/todo/<int:pk>/toggle/', views.todo_toggle, name='todo_toggle'),
    path('tools/todo/<int:pk>/delete/', views.todo_delete, name='todo_delete'),
    path('tools/budget/', views.budget_tracker, name='budget_tracker'),
    path('tools/budget/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
]

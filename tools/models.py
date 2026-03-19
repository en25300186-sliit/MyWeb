from django.db import models
from django.contrib.auth.models import User


class StudyNote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class TodoItem(models.Model):
    PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todos')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    due_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['completed', '-created_at']

    def __str__(self):
        return self.title


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('food', 'Food'), ('transport', 'Transport'), ('education', 'Education'),
        ('entertainment', 'Entertainment'), ('utilities', 'Utilities'), ('other', 'Other'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    date = models.DateField()
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.title} - {self.amount}"


class TimetableEntry(models.Model):
    EVENT_TYPE_CHOICES = [
        ('lecture', 'Lecture'),
        ('lab', 'Lab'),
        ('tutorial', 'Tutorial'),
        ('exam', 'Exam'),
        ('meeting', 'Meeting'),
        ('other', 'Other'),
    ]
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    COLOR_CHOICES = [
        ('#1a73e8', 'Blue'), ('#e53935', 'Red'), ('#43a047', 'Green'),
        ('#fb8c00', 'Orange'), ('#8e24aa', 'Purple'), ('#00acc1', 'Cyan'),
        ('#f4511e', 'Deep Orange'), ('#6d4c41', 'Brown'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='timetable_entries')
    title = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='lecture')
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, choices=COLOR_CHOICES, default='#1a73e8')

    # Schedule: weekly recurring OR one-time on a specific date
    is_weekly = models.BooleanField(default=True)
    day_of_week = models.IntegerField(choices=DAY_CHOICES, null=True, blank=True)
    specific_date = models.DateField(null=True, blank=True)

    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return self.title

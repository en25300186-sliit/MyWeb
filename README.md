# EngiHub – Tools for Engineering Students

A Django web application providing productivity and engineering tools for students.

## Features

- **Unit Converter** – Length, mass, temperature, area, volume, speed, pressure, energy
- **GPA Calculator** – Add courses with credit hours and grades; calculates cumulative GPA
- **Resistor Calculator** – Color band decoder with SVG visual
- **Study Notes** – Create, edit, delete notes organized by subject
- **To-Do List** – Tasks with priority levels and due dates
- **Budget Tracker** – Expense tracking with Chart.js doughnut chart
- **Study Timer** – Pomodoro-style timer (25 min work / 5 min break)
- **User Auth** – Register, login, logout using Django's built-in auth

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# (Optional) Create a superuser for the admin panel
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Then open http://127.0.0.1:8000/ in your browser.

## Project Structure

```
MyWeb/
├── manage.py
├── requirements.txt
├── myweb/          # Project config (settings, urls, wsgi, asgi)
├── accounts/       # Auth app (register, login, logout)
├── tools/          # Main app (all tools + dashboard)
├── templates/      # Global base.html template
└── static/         # CSS and JS assets
```

## Tech Stack

- **Backend**: Django 4.2, SQLite
- **Frontend**: Bootstrap 5.3, Bootstrap Icons, Chart.js
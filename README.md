# IP Aqua Tech

**Solar-Powered Drinking Water Filtration Monitoring System**

A professional web-based monitoring application built with Django 5 for real-time tracking of water quality, solar power, filtration status, maintenance, and system health.

## Features

- **User Authentication** – Login, logout, change password, role-based access (Admin / Operator)
- **Dashboard** – System status, KPI cards, Chart.js graphs, active alerts
- **Water Quality Monitoring** – pH, TDS, turbidity, temperature, flow, pressure, auto Normal/Warning/Critical classification
- **Solar Power Monitoring** – Panel voltage/current/power, battery %, charging status
- **Filtration Monitoring** – Filter life, condition, pump & UV status
- **Water Production** – Daily / weekly / monthly / total production
- **Maintenance Management** – Schedules, technicians, history, status tracking
- **Alerts & Notifications** – Auto-generated alerts for quality, filters, battery, tank, pump
- **Reports** – Daily / weekly / monthly / annual export to PDF and Excel
- **User Management** – Admin CRUD for users, roles, activate/deactivate
- **IoT / Firebase** – ESP32 → Firebase RTDB or Django API, device registry, sync, live snapshot
- **Predictions** – Rain forecast (Open-Meteo) + risk of malabo na tubig-bukal (turbidity)

## Tech Stack

| Layer      | Technology                          |
|-----------|--------------------------------------|
| Backend   | Python 3.10+, Django 5.1             |
| Frontend  | Bootstrap 5, Chart.js, Font Awesome  |
| Database  | SQLite (default), MySQL supported    |
| Reports   | ReportLab (PDF), openpyxl (Excel)    |

## Project Structure

```
Capstone/
├── accounts/          # Auth, custom User, user management
├── dashboard/         # Main dashboard & chart API
├── monitoring/        # Water quality, tanks, pumps, production
├── solar/             # Solar system & battery
├── filters/           # Filtration units
├── maintenance/       # Maintenance tasks
├── reports/           # Report generation (PDF/Excel)
├── notifications/     # Alerts
├── templates/         # HTML templates
├── static/            # CSS, JS
├── media/             # Uploaded reports
├── ipaquatech/        # Project settings & root URLs
├── manage.py
└── requirements.txt
```

## Installation

### 1. Prerequisites

- Python 3.10 or higher
- pip

### 2. Clone / open project

```bash
cd Capstone
```

### 3. Create virtual environment

```bash
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
venv\Scripts\activate.bat

# Linux / macOS
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

> **MySQL note:** `mysqlclient` is listed for MySQL support. On Windows you may need a prebuilt wheel or skip it if using SQLite only:
> ```bash
> pip install Django==5.1.6 openpyxl reportlab pillow python-dateutil
> ```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Seed sample data

```bash
python manage.py seed_data
```

This creates demo users, water quality readings, solar logs, filters, tanks, pumps, maintenance tasks, and alerts.

### 7. Start development server

```bash
python manage.py runserver
```

Open: **http://127.0.0.1:8000/**

## Default Login Credentials

| Role     | Username    | Password     |
|----------|-------------|--------------|
| Admin    | `admin`     | `admin123`   |
| Operator | `operator`  | `operator123`|
| Tech     | `technician`| `tech123`    |

## MySQL Configuration (Optional)

Set environment variables before running:

```bash
# Windows PowerShell
$env:USE_MYSQL="True"
$env:MYSQL_DATABASE="ipaquatech"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="yourpassword"
$env:MYSQL_HOST="localhost"
$env:MYSQL_PORT="3306"

python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Or edit `USE_MYSQL` and credentials in `ipaquatech/settings.py`.

## Running Tests

```bash
python manage.py test
```

## Theme Colors

| Color        | Usage                    |
|--------------|--------------------------|
| Aqua Blue    | Primary UI (`#0a4d68`)   |
| White        | Cards / content          |
| Dark Blue    | Sidebar (`#06283d`)      |
| Green        | Normal status            |
| Yellow       | Warning status           |
| Red          | Critical status          |

## Security Notes

- CSRF protection enabled on all forms
- Password validators active
- Role-based access via `@admin_required` decorator
- Login required for all monitoring pages
- Change `SECRET_KEY` and set `DEBUG=False` for production

## License

Academic / Capstone project use.

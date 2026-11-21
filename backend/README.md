
# FSC Lost & Found — Django Backend

Python/Django REST API for the FSC Lost & Found application.

## Requirements

- Python 3.13
- pip
- Git

## Setup

From the repository root:

### macOS / Linux

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run the virtual environment's
Python executable directly instead.

### Environment Configuration

Create a local `.env` file from the provided example.

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

Generate a unique Django secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Open `.env` and replace `replace_with_your_own_generated_key`
with the generated value.

Django automatically loads `.env` through `python-dotenv`.

Never commit `.env` or share your secret key.

### SQLite Database

The backend uses SQLite by default. Django stores the database at:

```text
backend/db.sqlite3
```

This file is local development data and is ignored by Git. SQLite is suitable
for development and testing. PostgreSQL may be used for a production deployment
without changing the application models.

### Initialize and Run the Backend

After configuring your `.env` file, install the dependencies and initialize the SQLite database:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Django creates the SQLite database and built-in tables through migrations.


## Health-check endpoint

Start the server and visit:

http://127.0.0.1:8000/api/health/

Expected JSON response:

```json
{
  "status": "ok",
  "service": "FSC Lost & Found API"
}
```

## Automated tests

```bash
python manage.py test
```

The test suite verifies the health endpoint, account passwords, report
ownership, claim ownership, and incident-date validation.

## Database

The backend uses SQLite for local development and testing. Report data is
stored in Django models in the `reports` app:

- `Profile`: student or campus-security account details
- `Report`: lost/found item submissions
- `ReportAttachment`: report image or document uploads
- `Match`: possible relationship between a lost report and found report
- `Claim`: ownership claim associated with a report and claimant

Usernames and passwords use Django's built-in authentication model. Passwords
are hashed rather than stored as plain text.

## API endpoints

- `GET /api/session/`
- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET|POST /api/reports/`
- `GET /api/claims/`
- `POST /api/claims/create/`
- `POST /api/attachments/upload/`
- `GET /api/health/`

The Django admin at `/admin/` provides staff review and report, match, and claim
management.

## Security

- Never commit `.env` files, API keys, or credentials.
- The Django development server is not intended for production.
- Authentication, permissions, and deployment security must be
  configured before the backend is made publicly accessible.
```

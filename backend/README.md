
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


### Initialize and Run the Backend

After configuring your `.env` file, run:

```bash
python manage.py migrate
python manage.py runserver
```


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

The initial test verifies that the health-check endpoint returns
HTTP 200 with the expected JSON response.

## Database

SQLite is used for local development.

Run `python manage.py migrate` to create the initial Django tables.

The local `db.sqlite3` file is excluded from Git.

Lost and found report models will be added in a future development task.

## Security

- Never commit `.env` files, API keys, or credentials.
- The Django development server is not intended for production.
- Authentication, permissions, and deployment security must be
  configured before the backend is made publicly accessible.
```

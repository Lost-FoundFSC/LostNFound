
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

## Lost and found reports

Each submitted form is saved as one row in the database:

| Table | What is in it |
|---|---|
| `reports_lostreport` | Open lost reports |
| `reports_foundreport` | Open found reports |
| `reports_archivedreport` | Finished reports (returned, closed, or cancelled), lost and found together, with a `report_type` column |

Keeping finished reports in the archive means matching only has to look
at open reports.

### Form IDs

Every report gets a form ID when it is submitted:

- Lost reports: `L#` + 9 digits, for example `L#384834901`
- Found reports: `F#` + 9 digits, for example `F#238832420`

The ID is random, never reused, and stays the same when a report moves
to the archive and back. It is the ID to use everywhere: on the
confirmation screen, on the student dashboard, for Campus Security, and
when comparing reports.

`#` cannot be used inside a URL, so URLs use the ID without it
(`/api/reports/progress/L384834901/`). Lowercase IDs also work.

### Endpoints

| Method | URL | Who | Purpose |
|---|---|---|---|
| POST | `/api/reports/` | Anyone | Submit the report form. Returns the form ID. |
| GET | `/api/reports/progress/<form ID>/` | Anyone with the form ID | Progress of one report (no personal details). Limited to 30 lookups a minute. |
| GET | `/api/reports/mine/` | Signed-in student | Progress of every report submitted with the student's email (open and archived), for the dashboard |
| GET | `/api/reports/lost/` | Campus Security | Open lost reports (`?status=possible_match` to filter) |
| GET | `/api/reports/found/` | Campus Security | Open found reports (same filter) |
| GET | `/api/reports/archive/` | Campus Security | Archived reports (`?type=lost`, `?semester=Fall 2026`) |
| GET | `/api/reports/<form ID>/` | Campus Security | Full report, open or archived |
| PATCH | `/api/reports/<form ID>/` | Campus Security | Change status, for example `{"status": "ready_for_pickup"}` |
| GET | `/api/reports/<form ID>/images/<image_id>/` | Campus Security | View one photo |

Example response after submitting:

```json
{"formId": "F#923356063", "reportType": "found", "status": "reported", "imageCount": 1}
```

The POST body uses the same camelCase field names as
`frontend/src/data/reportFields.js`. Validation:

- Name, email, and phone are required. The phone must have 10 digits
  (a leading +1 is allowed) and is stored as (516) 555-1234.
- The date (`incidentDate`) and campus location are optional, since
  people often only know roughly when or where. A date that is given
  cannot be in the future.
- The liability notice must be accepted.
- The category must be one of the form's categories.
- The RAM ID is optional, but if given it must be R plus 8 digits
  (for example R01234567). The full RAM ID is stored so security can
  check it in person.

### Map pin (future feature)

`mapLatitude` and `mapLongitude` are reserved for the upcoming campus
map. They are optional and stay empty until the map is added to the
form. When the map is ready, send the pin the user drops:

```json
{"mapLatitude": 40.752114, "mapLongitude": -73.427983}
```

Send both or neither. Campus Security sees the pin in the full report;
it is not shown in the public progress lookup.

### Report status

The stages match `REPORT_STAGES` in
`frontend/src/data/accountDemoData.js`.

Open (stays in the lost/found tables):

1. `reported`: new reports start here
2. `possible_match`
3. `under_verification`
4. `ready_for_pickup`

Done (moves to the archive):

- `returned`: the item went back to its owner
- `closed`: closed without the item being returned
- `cancelled`: the report was withdrawn

When a report is set to a done status it is moved to the archive with
its photos, and `completedAt` and `archiveSemester` (for example
"Fall 2026") are filled in. Setting an archived report back to an open
status moves it back. Only the status can be changed through PATCH; the
rest of the report stays as submitted.

The student dashboard endpoint (`/mine/`) needs real sign-in, which is
not connected yet. It matches reports by the signed-in user's email.

### Photos

Reports can include up to 5 photos. To send photos, submit the form as
`multipart/form-data` (a `FormData` object in JavaScript) and add each
file under the field name `images`. Plain JSON submissions without photos
still work.

```js
const formData = new FormData()
Object.entries(values).forEach(([key, value]) => formData.append(key, value))
photoFiles.forEach(file => formData.append('images', file))
await fetch('http://localhost:8000/api/reports/', { method: 'POST', body: formData })
// Do not set Content-Type yourself; the browser adds it.
```

Rules:

- JPEG, PNG, or WebP only, up to 5 MB each.
- If any photo is invalid, the whole report is rejected so nothing is
  half-saved.
- Each photo is re-saved on upload. This turns it upright and removes
  metadata such as the GPS location phones add.
- Files are stored under `backend/media/report_images/<lost or found>/`
  with random names. The original file name is not kept.
- Photos are not publicly reachable. Only Campus Security can open them,
  through the image URLs listed in a report's `images` field or the
  report's page in the admin site.

Photos are stored in their own tables (`reports_lostreportimage`,
`reports_foundreportimage`, and `reports_archivedreportimage`), linked
to a report by `report_id`.

### Campus Security accounts

Only members of the **Campus Security** group (and superusers) can view
reports or change their status. The group is created automatically by
`python manage.py migrate`.

To set up a security account:

1. `python manage.py createsuperuser` (once, for yourself)
2. Go to http://127.0.0.1:8000/admin/ and open **Users**, then **Add user**.
3. On the new user, add the **Campus Security** group.
4. Tick **Staff status** if they should also use the admin site.

To try the API in a browser, log in at http://127.0.0.1:8000/api-auth/login/
and then open http://127.0.0.1:8000/api/reports/lost/.

In the admin site, security can search by form ID, name, email, or RAM
ID, filter by status, and use the actions menu to move reports to the
next stage, archive them, or reopen archived ones.

### Exporting reports

To export reports as JSON files (for example, to feed to a matching model):

```bash
python manage.py dumpdata reports.LostReport --indent 2 > lost.json
python manage.py dumpdata reports.FoundReport --indent 2 > found.json
python manage.py dumpdata reports.ArchivedReport --indent 2 > archive.json
```

The React dev server (`http://localhost:5173`) is allowed through CORS.
Set `CORS_ALLOWED_ORIGINS` in `.env` to allow other origins.

## Security

- Never commit `.env` files, API keys, or credentials.
- The Django development server is not intended for production.
- Authentication, permissions, and deployment security must be
  configured before the backend is made publicly accessible.
```

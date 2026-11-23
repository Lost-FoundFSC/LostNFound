
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
| GET | `/api/reports/<lost form ID>/matches/` | Anyone with the lost form ID | All ranked, unlinked found reports with nonzero comparison scores and limited public item details. Limited to 20 lookups a minute. |
| GET | `/api/reports/mine/` | Signed-in student | Progress of every report submitted with the student's email (open and archived), for the dashboard |
| GET | `/api/reports/lost/` | Campus Security | Open lost reports (`?status=possible_match` to filter) |
| GET | `/api/reports/found/` | Campus Security | Open found reports (same filter) |
| GET | `/api/reports/archive/` | Campus Security | Archived reports (`?type=lost`, `?semester=Fall 2026`) |
| GET | `/api/reports/<form ID>/` | Campus Security | Full report, open or archived |
| PATCH | `/api/reports/<form ID>/` | Campus Security | Change status, for example `{"status": "ready_for_pickup"}`, and/or match it, for example `{"matchedFormId": "F#238832420"}` |
| GET | `/api/reports/<form ID>/images/<image_id>/` | Campus Security | View one photo |

Example response after submitting:

```json
{"formId": "F#923356063", "reportType": "found", "status": "reported", "imageCount": 1}
```

The POST body uses the same camelCase field names as
`frontend/src/data/reportFields.js`. Validation:

- Lost reports: name, email, and phone are required so Campus Security
  can reach the owner.
- Found reports: name, email, and phone are optional. The finder has
  handed the item in, so everything needed is already on the form.
- When contact details are given, they are checked: a valid email, and a
  phone number with 10 digits (a leading +1 is allowed), stored as
  (516) 555-1234.
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

### Matching a lost report to a found report

When Campus Security confirms that a lost report and a found report are the
same item, they link the two. Each report then stores the other's form ID
in `matchedFormId` (`matched_form_id` in the database).

- API: `PATCH /api/reports/L384834901/` with
  `{"matchedFormId": "F#238832420"}`. Send `""` to remove the match. A
  status can be sent in the same request, for example
  `{"matchedFormId": "F#238832420", "status": "returned"}`.
- Admin: open either report, type the other form ID in **Matched form ID**,
  and save. Clear the box to remove the match.

Rules:

- Only a lost report and a found report can be matched, one to one.
- Marking either report **Returned** marks both returned and moves both to
  the archive. In the archive each still shows the other's form ID.
- Reopening a returned report reopens its returned match too.
- Other status changes (possible match, ready for pickup, closed, and so
  on) only change the one report.
- The match is not shown in the public progress lookup.

### Potential matches for a lost report

The React Possible Matches page requests
`GET /api/reports/L384834901/matches/` using the lost report's form ID.
The response contains the lost item's name and category plus all matching
unlinked found reports with their form ID, item name, category, location,
date, and a `matchScore` from 0 to 100. Contact details, descriptions, and
photos are not returned. The endpoint is public and rate-limited; treat the
lost report form ID as private.

The score is a heuristic comparison of item-name similarity, category,
location, and date when available. It is not an AI result or a calibrated
probability of ownership. Campus Security must verify a match.

#### Sample data for testing

Run `python manage.py seed_sample_reports` after migrations to add eight
synthetic reports to the local database. The command uses stable form IDs,
skips reports that already exist, and refuses to run unless `DEBUG=True`.
It does not delete or update existing reports. The API tests also build
reports from a shared sample form in `reports/tests.py`; the separate
matching evaluation dataset in `reports/ai_evaluation/golden_tests.json`
contains the 15 sample lost/found pairs below. Its `expected_match` value
is the evaluation label, not a result produced by the live percentage
matcher.

On Windows, run the command from the `backend` directory with:

```powershell
py manage.py seed_sample_reports
```

| # | Lost-item sample (name; category; color; description) | Found-item sample (name; category; color; description) | Expected match |
|---:|---|---|:---:|
| 1 | Apple AirPods Pro; Electronics; White; AirPods Pro with a small scratch on the charging case | Apple AirPods Pro; Electronics; White; White AirPods Pro with a scratch on the charging case | Yes |
| 2 | Nike Backpack; Bags; Black; Black Nike backpack with a red zipper | Nike Backpack; Bags; Black; Black Nike backpack with a red zipper | Yes |
| 3 | Samsung Galaxy S24; Electronics; Black; Samsung phone with a cracked screen | iPhone 15; Electronics; Blue; Blue iPhone with a clear case | No |
| 4 | Stanley Water Bottle; Personal Items; Pink; Pink Stanley bottle with a flower sticker | Stanley Water Bottle; Personal Items; Pink; Pink Stanley bottle with a flower sticker | Yes |
| 5 | Dell Laptop Charger; Electronics; Black; Dell charger with a blue connector tip | HP Laptop Charger; Electronics; Black; HP charger with a blue connector tip | No |
| 6 | Adidas Hoodie; Clothing; Gray; Gray Adidas hoodie with a small coffee stain on the sleeve | Adidas Hoodie; Clothing; Gray; Gray Adidas hoodie with a coffee stain on the sleeve | Yes |
| 7 | Casio Watch; Accessories; Silver; Silver Casio watch with a scratched face | Casio Watch; Accessories; Gold; Gold Casio watch with a clean face | No |
| 8 | Blue Notebook; School Supplies; Blue; Blue spiral notebook with a math sticker | Blue Notebook; School Supplies; Blue; Blue spiral notebook with a math sticker | Yes |
| 9 | Apple MacBook Air; Electronics; Silver; Silver MacBook Air with a star sticker | Apple MacBook Pro; Electronics; Space Gray; MacBook Pro with no stickers | No |
| 10 | Black Umbrella; Accessories; Black; Black umbrella with a wooden handle | Black Umbrella; Accessories; Black; Black umbrella with a wooden handle | Yes |
| 11 | Sony Headphones; Electronics; Black; Sony headphones with a broken left ear cushion | Sony Headphones; Electronics; Black; Sony headphones with a broken left ear cushion | Yes |
| 12 | Nike Sneakers; Shoes; White; White Nike sneakers with blue laces | Adidas Sneakers; Shoes; White; White Adidas sneakers with black laces | No |
| 13 | Student ID Card; Personal Items; Green; Student ID card with a cracked plastic holder | Student ID Card; Personal Items; Green; Student ID card with a cracked plastic holder | Yes |
| 14 | Hydro Flask Bottle; Personal Items; Purple; Purple Hydro Flask with a dent on the bottom | Hydro Flask Bottle; Personal Items; Purple; Purple Hydro Flask with no dents | No |
| 15 | Car Keys; Accessories; Black; Toyota car key with a red keychain | Car Keys; Accessories; Black; Toyota car key with a red keychain | Yes |

These are evaluation examples, not all valid submissions to `POST
/api/reports/`: the live API categories are `Electronics`, `Clothing`,
`Accessories`, `Wallets & IDs`, `Books`, and `Other`. In particular,
`Bags`, `Personal Items`, `School Supplies`, and `Shoes` in the evaluation
dataset are not accepted API category values. The evaluation fixtures also
use `color`, while the report API has no separate color field.

The seed command creates these eight reports. Form IDs are fixed by the
command so every developer can test the same IDs:

| Form ID | Type | Category | Item and unique identifying detail |
|---|---|---|---|
| `L#312198494` | Lost | Electronics | Navy Sony headphones with a silver star sticker on the left ear cup and initials MK under the headband. |
| `F#471000254` | Found | Accessories | Brass dorm key with a scratched round head and an orange rocket-shaped keychain. |
| `L#142196003` | Lost | Clothing | Charcoal canvas backpack with a turquoise dinosaur patch and a missing zipper pull on the left side. |
| `F#889760940` | Found | Clothing | Olive carry-on duffel with a white ram-shaped patch on the side handle and a red luggage tag. |
| `L#800000001` | Lost | Books | Calculus textbook with a red bicycle sticker on the back cover and pages 42-48 highlighted in green. |
| `F#800000001` | Found | Books | Calculus textbook with a red bicycle sticker and green highlighting on pages 42-48. |
| `L#800000002` | Lost | Wallets & IDs | Brown leather card wallet with a tiny brass compass charm stitched beside the inside ID window. |
| `F#800000002` | Found | Wallets & IDs | Brown leather card wallet with a small brass compass charm next to the clear ID window. |

The lost reports use synthetic `example.com` email addresses and `555-0101`
through `555-0104` phone numbers. The key is categorized as `Accessories`;
bags and carry-ons use `Clothing`. These are local-only test records, not
production reports.

To create additional test reports through the API, submit valid report
forms. This example follows the shared base payload in `reports/tests.py`;
change `reportType` to `found` to create a found report (contact fields are
optional for found reports). The API assigns the form ID in its response:

```json
{
  "reportType": "lost",
  "fullName": "Jane Doe",
  "email": "doej@farmingdale.edu",
  "studentId": "R01234567",
  "phone": "516-555-1234",
  "category": "Electronics",
  "itemName": "Black AirPods case",
  "description": "Scratch on lid",
  "estimatedValue": "",
  "incidentDate": "",
  "incidentTime": "",
  "campusLocation": "Greenley Library",
  "locationDetails": "2nd floor",
  "liabilityAccepted": true
}
```

Submit one lost report and one or more found reports with `POST
/api/reports/`, then request `GET /api/reports/<lost form ID>/matches/`
using the lost report ID returned by the API. The live matcher compares
item name, category, location, and date; it does not use description or a
separate color value.

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

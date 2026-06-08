Dynamic Entities — Usage

**Setup**
- **Python:** 3.8+ recommended. Install dependencies:

```bash
pip install -r requirements.txt
```

- **Environment:** create a `.env` file or export the following environment variables used by `obp_client.py`:
  - **OBP_USERNAME:** OBP username
  - **OBP_PASSWORD:** OBP password
  - **OBP_CONSUMER_KEY:** consumer key for DirectLogin
  - **OBP_HOSTNAME:** (optional) OBP base URL; defaults in `obp_client.py`

**Files**
- **`parse_minimum_fields.py`**: Parse the minimal field matrix Excel (`min_field_matrix.xlsx` by default) and optionally create dynamic entities on OBP.
- **`main.py`**: High-level management script that deletes objects, deletes matching dynamic entities, then recreates entities defined in `dynamic_entities.py`.

**`parse_minimum_fields.py` — Usage**

This creates the entities from the minimal field matrix Excel file, exported from the [Google Sheet template](https://docs.google.com/spreadsheets/d/1MVoMuVCN-kAACbu31CEtF2hd-xQ-d0L7-8m29LSX14E/edit?gid=0#gid=0).

- **Run locally (print parsed entities):**

```bash
python3 parse_minimum_fields.py [path/to/min_field_matrix.xlsx]
```

- **Create dynamic entities on OBP:**

```bash
python3 parse_minimum_fields.py [path/to/min_field_matrix.xlsx] --create
```

- **Update existing dynamic entities on OBP:**

```bash
python3 parse_minimum_fields.py [path/to/min_field_matrix.xlsx] --update
```

`--update` looks up each existing dynamic entity by name and updates its definition in place (entities not found on OBP are skipped). Use `--create` for fresh entities and `--update` to modify ones that already exist.

- **Options:**
  - **`file`** (positional): Path to the Excel file. Defaults to `min_field_matrix.xlsx`.
  - **`--create`**: If set, the script will POST created entity definitions to the OBP management API.
  - **`--update`**: If set, update existing dynamic entities (matched by name) instead of creating new ones.
  - **`--token`**: DirectLogin token to use (overrides token from `obp_client.py`).
  - **`--host`**: OBP host/base URL to use (overrides `OBP_HOSTNAME`).
  - **`--yes`**: When used with `--create`, skip interactive confirmation prompt.

> **Note:** `--create` only *creates* — it does not delete existing entities or objects first. To do a clean wipe-and-recreate, use `main.py` (which deletes objects and entity definitions before recreating), but note that `main.py` rebuilds from the hardcoded entities in `dynamic_entities.py`, **not** from a spreadsheet.

Notes about parsing behavior:
- Column A is used for field names and `entity:` rows start new entities.
- Column D is preserved as the `value` (type) in the parsed attribute dict.
- Column F is used as the `description` for attributes (and the entity-level description on `entity:` rows).
- Column G is used as the `example` value for attributes when present.
- Field names are sanitized: dots and other disallowed characters are replaced by underscore (`_`), repeated underscores are collapsed, and leading/trailing underscores are removed.
- Example strings from column G have surrounding single or double quotes stripped.

**Re-create the entities (delete then create from the spreadsheet)**

A clean wipe-and-recreate driven entirely by the spreadsheet (this is what `main.py` does *not* do — `main.py` is tied to the hardcoded list in `dynamic_entities.py`):

1. **Parse and save** the entity list to `entities_output.txt`:

```bash
python3 parse_minimum_fields.py min_field_matrix.xlsx
# answer "y" when prompted, accept the default filename entities_output.txt
```

2. **Delete** those entities and all their records on OBP with `delete_entities.py`:

```bash
python3 delete_entities.py            # reads entities_output.txt by default; prompts for confirmation
python3 delete_entities.py --yes      # skip the confirmation prompt
```

3. **Re-create** the entities from the spreadsheet:

```bash
python3 parse_minimum_fields.py min_field_matrix.xlsx --create --yes
```

Notes:
- `delete_entities.py` deletes exactly the entities listed in `entities_output.txt` (one per `Entity:` line). If an entity was **renamed** in the spreadsheet, the old name is *not* in the file and will be left on OBP as an orphan — delete it separately.
- Always regenerate `entities_output.txt` (step 1) after editing the spreadsheet, so the delete list matches what you are about to create.
- `delete_entities.py` options: `file` (positional, default `entities_output.txt`), `--yes` (skip confirmation), `--token` (override the DirectLogin token).

**Create dummy data**

`create_dummy_data.py` creates one sample object per entity, driven by the same spreadsheet. Run it *after* the entities exist on OBP (see "Re-create the entities" above):

```bash
python3 create_dummy_data.py [path/to/min_field_matrix.xlsx] [--token TOKEN]
```

- **`file`** (positional): spreadsheet path. Defaults to `min_field_matrix.xlsx`.
- **`--token`**: DirectLogin token (overrides the token from `obp_client.py`).

How it works:
- **Values come from the spreadsheet** — each field is populated from its column G `example` value, coerced to the field's declared type (string, `integer`, `number`, `boolean`, `json`, `DATE_WITH_DAY`).
- **Foreign keys are made valid** — any `<entity>_id` field is overwritten with the real id of the referenced object, so the dummy data is referentially consistent (e.g. `activity.operator_id` points at the created `operator`, and `audit_report` links to the operator, activity, scheme, body, plans and certificate).
- Entities that own an `<entity>_id` field get a canonical id taken from the spreadsheet example; the verification/report entities without one receive an OBP-generated UUID.
- The field `compliance_certificate_id` (which does not follow the `<entity>_id` convention) is mapped to `certificate_of_compliance` via an explicit alias in the script (`FK_ALIASES`).

Notes:
- It creates **one record per entity**. To create more (e.g. several parcels under one activity), extend the payload loop in `main()`.
- It is fully spreadsheet-driven — it does **not** use the hardcoded entities in `dynamic_entities.py`.

**`main.py` — Usage**
- Run the management workflow (delete objects, delete entity definitions, recreate entities):

```bash
python3 main.py
```

- `main.py` uses credentials and host configured in environment (via `obp_client.py`). It does not accept CLI args; set the environment first.

**Tips & Validation**
- The parser attempts to coerce example values to appropriate types (integer, number, boolean, array/object via JSON) before sending to OBP so the `example` field matches OBP validation expectations.
- If you run with `--create` and receive a 400 validation error, inspect the printed parsed entities to find which property's `example` is mismatched.

**Example workflow**
1. Ensure env vars set (or a `.env` file present).
2. Inspect parsing output:

```bash
python3 parse_minimum_fields.py
```

3. Create entities on OBP (confirm with `--yes` or interactively):

```bash
python3 parse_minimum_fields.py --create --yes
```

4. Use `main.py` to clean and recreate system entities defined in `dynamic_entities.py`:

```bash
python3 main.py
```

**Where to look for issues**
- Parsed entities printed by `parse_minimum_fields.py` show the exact `value` and `example` used to build the dynamic entity schema.
- If a field example must be a number, ensure column H contains an unquoted numeric value (the parser will coerce when possible).

If you want me to add example `.env` content, a quick test script, or adjust any parsing detail, tell me which part to update next.


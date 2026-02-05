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

- **Options:**
  - **`file`** (positional): Path to the Excel file. Defaults to `min_field_matrix.xlsx`.
  - **`--create`**: If set, the script will POST created entity definitions to the OBP management API.
  - **`--token`**: DirectLogin token to use (overrides token from `obp_client.py`).
  - **`--host`**: OBP host/base URL to use (overrides `OBP_HOSTNAME`).
  - **`--yes`**: When used with `--create`, skip interactive confirmation prompt.

Notes about parsing behavior:
- Column A is used for field names and `entity:` rows start new entities.
- Column D is preserved as the `value` in the parsed attribute dict.
- Column H is used as the `example` value for attributes when present.
- Field names are sanitized: dots and other disallowed characters are replaced by underscore (`_`), repeated underscores are collapsed, and leading/trailing underscores are removed.
- Example strings from column H have surrounding single or double quotes stripped.

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


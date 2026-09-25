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
  - **OBP_ENTITY_SPACE_ID:** (optional) the bank id (aka Space) that owns all the OGCR dynamic entities. Defaults to `ogcr`; set it to the empty string for system level. See "Where the entities live" below.

**Files**
- **`parse_minimum_fields.py`**: Parse the minimal field matrix Excel (`min_field_matrix.xlsx` by default) and optionally create dynamic entities on OBP.
- **`main.py`**: High-level management script that deletes objects, deletes matching dynamic entities, then recreates entities defined in `dynamic_entities.py`.
- **`check_min_field_matrix.py`** / **`.sh`**: Check the spreadsheet for problems before creating anything (offline, read-only).
- **`check_login_and_roles.py`** / **`.sh`**: Check DirectLogin works and the user holds the Roles the entities need (read-only).
- **`create_entitlements.py`** / **`.sh`**: Grant the logged in user those Roles.
- **`dry_run_create_ogcr_entities.py`** / **`.sh`**: DRY RUN of `recreate_ogcr_entities.sh` — says what it would do, changes nothing.
- **`create_space_bank.py`** / **`.sh`**: Create the `OBP_ENTITY_SPACE_ID` bank if it doesn't exist.
- **`obp_space.py`**: The one place that builds dynamic-entity URLs and Role bank ids from `OBP_ENTITY_SPACE_ID`.

**Where the entities live (`OBP_ENTITY_SPACE_ID`)**

All OGCR entities live in one place: either at system level, or under one bank (OBP also calls a bank a *Space*). Set `OBP_ENTITY_SPACE_ID` in `.env` to choose; unset, it is `ogcr`, the same default as OGCR-App and OGCR-chain-cache:

| `OBP_ENTITY_SPACE_ID` | Definitions | Records | Roles granted at bank id |
|---|---|---|---|
| empty | `/obp/<v>/management/system-dynamic-entities` | `/obp/dynamic-entity/[public/]<entity>` | `SYS` |
| `ogcr` (default) | `/obp/<v>/management/banks/ogcr/dynamic-entities` | `/obp/dynamic-entity/banks/ogcr/[public/]<entity>` | `ogcr` |

Every script (create, update, delete, dummy data, Roles, join indexes, audit log) builds its URLs from `obp_space.py`, so they always agree, and deleting only ever touches entities in the configured space. This replaces the old `OBP_ENTITY_PREFIX`, which has been removed.

The bank must exist before entities can be created in it. `recreate_ogcr_entities.sh` creates it if it's missing, or run it on its own:

```bash
./create_space_bank.sh                              # full name defaults to "OGCR <bank id>"
./create_space_bank.sh --full-name "OGCR Registry"
```

Creating a bank needs the Role `CanCreateBank`. Anything that reads the entities (e.g. OGCR-App) must use the same bank id. See `SPACE_LEVEL_VERSIONING_PLAN.md` for the background.

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

**Check the spreadsheet (`check_min_field_matrix.sh`)**

Run this after editing the spreadsheet and before `--create`. It works offline (no login, changes nothing), reads the sheet exactly as `parse_minimum_fields.py` does, and reports each problem with its Excel cell — things the parser would otherwise drop or change silently.

```bash
./check_min_field_matrix.sh                         # checks min_field_matrix.xlsx
./check_min_field_matrix.sh other.xlsx --strict     # fail on warnings too
```

Possible errors it can report:
- entity name OBP rejects (e.g. contains a space) or defined twice
- entity with no fields ticked in column B or C (the parser drops it)
- unknown type in column D, or a misspelt `reference:` (e.g. `referece:`) — would become a string
- `reference:<entity>` to an entity not defined in the sheet (and not built into OBP) — would become a string
- two fields in one entity that end up with the same name

Possible warnings it can report:
- no `END_OF_FILE` row in column A
- ticked field with an empty type
- field name changed by sanitising (e.g. `monitoring period` → `monitoring_period`)
- example in column G that does not fit its type (integer, number, boolean, `DATE_WITH_DAY`, json)
- type in the wrong case (e.g. `Integer`)

The output lists only the problems actually found (`ERRORS FOUND` / `WARNINGS FOUND`). Exit code: `0` no errors, `1` errors (or warnings with `--strict`).

**Re-create the entities (delete then create from the spreadsheet)**

**Preview it first with a DRY RUN.** `./dry_run_create_ogcr_entities.sh [path/to/min_field_matrix.xlsx]` walks the same steps as `recreate_ogcr_entities.sh` in the same space, but only reads (the sheet, and GET requests to OBP). Every line starts with `[DRY RUN]`, and it reports: problems in the sheet; whether the space's bank would be created; each entity it would delete, with its record count; entities in the space it would leave alone; each entity it would create; the example data; and the Roles `create_entitlements.sh` would still need to grant. It doesn't rewrite `entities_output.txt`.

`recreate_ogcr_entities.sh` itself starts by showing the host, the space (`OBP_ENTITY_SPACE_ID`) and the sheet, and asks you to type `yes` before it changes anything. Pass `--yes` to skip the question in automation; without a terminal and without `--yes` it stops.

A clean wipe-and-recreate driven entirely by the spreadsheet (this is what `main.py` does *not* do — `main.py` is tied to the hardcoded list in `dynamic_entities.py`):

1. **Parse and save** the entity list to `entities_output.txt`:

```bash
python3 parse_minimum_fields.py min_field_matrix.xlsx --save   # non-interactive
# or run without --save and answer "y" at the prompt (default filename entities_output.txt)
```

2. **Delete** those entities and all their records on OBP with `delete_ogcr_entities.py`:

```bash
python3 delete_ogcr_entities.py            # reads entities_output.txt by default; prompts for confirmation
python3 delete_ogcr_entities.py --yes      # skip the confirmation prompt
```

3. **Re-create** the entities from the spreadsheet:

```bash
python3 parse_minimum_fields.py min_field_matrix.xlsx --create --yes
```

Notes:
- `delete_ogcr_entities.py` deletes exactly the entities listed in `entities_output.txt` (one per `Entity:` line) and leaves all other dynamic entities on the instance untouched. If an entity was **renamed** in the spreadsheet, the old name is *not* in the file and will be left on OBP as an orphan — delete it separately. To wipe **every** dynamic entity instead, use `delete_all_dynamic_entities.py`.
- Deletion runs in repeated passes so reference (foreign-key) constraints between entities don't block a clean delete, and it exits non-zero if anything it was asked to delete survives.
- Always regenerate `entities_output.txt` (step 1) after editing the spreadsheet, so the delete list matches what you are about to create.
- `delete_ogcr_entities.py` options: `file` (positional, default `entities_output.txt`), `--yes` (skip confirmation), `--token` (override the DirectLogin token).

**Roles (`check_login_and_roles.sh`, `create_entitlements.sh`)**

Every entity needs Roles, all granted at the bank id of the space (`OBP_ENTITY_SPACE_ID`, or `SYS` for system level):
- definition Roles: `CanCreateDynamicEntityDefinition`, `CanDeleteDynamicEntityDefinition`, `CanGetDynamicEntityDefinitions`, `CanUpdateDynamicEntityDefinition`
- record Roles, per entity: `CanCreateDynamicEntityRecord_<entity>`, and the same for `Delete`, `Get` and `Update`

Check that login works and which Roles are missing (read-only):

```bash
./check_login_and_roles.sh                              # definition Roles + record Roles for every entity in entities_output.txt
./check_login_and_roles.sh --no-entities                # definition Roles only
./check_login_and_roles.sh --role CanGetAnyUser --role CanFoo@some-bank   # extra Roles too
./check_login_and_roles.sh --list                       # also print every Role the user holds
```

When `OBP_ENTITY_SPACE_ID` is set it also checks the bank exists. Exit code: `0` all present, `1` login failed, `2` Role(s) missing, `3` the bank does not exist.

Grant the logged in user any missing Roles (entities read from `entities_output.txt`, or pass another file):

```bash
./create_entitlements.sh
```

Roles already held come back as `409 already exists`, which is harmless. A record Role can only be granted once its entity exists on OBP (otherwise `400 Unknown role`), so run this after creating the entities. Granting Roles itself needs `CanCreateEntitlementAtAnyBank` (or `CanCreateEntitlementAtOneBank` at the space's bank id).

**Create dummy data**

`create_dummy_data.py` creates one sample object per entity, driven by the same spreadsheet. Run it *after* the entities exist on OBP (see "Re-create the entities" above):

```bash
python3 create_dummy_data.py [path/to/min_field_matrix.xlsx] [--token TOKEN]
```

- **`file`** (positional): spreadsheet path. Defaults to `min_field_matrix.xlsx`.
- **`--token`**: DirectLogin token (overrides the token from `obp_client.py`).
- **`--no-log`**: Do not write the audit trail to the `ogcr_dynamicentities_log` dynamic entity.

How it works:
- **Values come from the spreadsheet** — each field is populated from its column G `example` value, coerced to the field's declared type (string, `integer`, `number`, `boolean`, `json`, `DATE_WITH_DAY`).
- **Foreign keys are made valid** — any `<entity>_id` field is overwritten with the real id of the referenced object, so the dummy data is referentially consistent (e.g. `activity.operator_id` points at the created `operator`, and `audit_report` links to the operator, activity, scheme, body, plans and certificate).
- Entities that own an `<entity>_id` field get a canonical id taken from the spreadsheet example; the verification/report entities without one receive an OBP-generated UUID.
- The field `compliance_certificate_id` (which does not follow the `<entity>_id` convention) is mapped to `certificate_of_compliance` via an explicit alias in the script (`FK_ALIASES`).

- **The run is audited in OBP** — unless `--no-log` is given, the script ensures a dynamic entity named after this application, `ogcr_dynamicentities_log` (in the same space as the other entities), exists (defined in `ogcr_log_entity.py`) and writes one record to it per object: `entity_created` for each created object and `entity_failed` for each failed create (with the OBP error text). Each record carries `entity_name`, `entity_id`, `status`, `message`, a UTC `timestamp`, and a json `references` list describing **every** `reference:<x>` field on the entity and how it resolved — each item has `field`, `target`, `resolution` (`resolved` = a real created id was used; `fallback` = the spreadsheet example value was used because the target is a static OBP entity or one we don't create here) and the `value` posted. Logging is best-effort: if the log entity cannot be created or a record fails to POST, the data creation continues uninterrupted.

Notes:
- It creates **one record per entity**. To create more (e.g. several parcels under one activity), extend the payload loop in `main()`.
- It is fully spreadsheet-driven — it does **not** use the hardcoded entities in `dynamic_entities.py`.

**Public read access (`EntityHasPublicAccess`)**

An entity can be opened for unauthenticated read — useful for open reference data such as the country list. Tick the **`EntityHasPublicAccess`** column (column Q) on the entity's `Entity: <name>` row in the spreadsheet; leave the field rows blank, because the flag is entity-level, not per field. `TRUE`, `1`, `Y` or a checkmark all count; blank or `FALSE` means not public.

The parser finds the column by *header text*, not position, so it can be moved and minor spelling differences (`hasPublicAccess`, `Entity Has Public Access`) still match. If the column is missing entirely — an older export — every entity simply defaults to not public.

A ticked entity is created with `"hasPublicAccess": true`, which gives it an extra route:

| Route | Who | What |
|---|---|---|
| `GET /obp/dynamic-entity/public/<entity>` | anyone, **no login** | read only, shared-pool rows only |
| `GET /obp/dynamic-entity/<entity>` | role holders | unchanged; 401 without authentication |
| any write to `/public/` | — | 404; there is no public write route |

The flag is only sent when it is switched on, so an OBP build that predates it is unaffected. See the `Dynamic-Entity-Access-Model` glossary entry on your OBP instance for the full access model (`hasPersonalEntity`, `hasCommunityAccess`, `useRowLevelAccess`, `authMode` and field-level roles); this flag is its "curated reference data" pattern — role holders maintain the data, everyone reads it.

Currently ticked: `country`, `technologies_practices_processes`.

**Fixtures (controlled vocabularies)**

Some entities are not examples but fixed lists of values the rest of the system selects from. These live in `fixtures.py`, not in the spreadsheet, and `create_dummy_data.py` writes the whole list instead of a single example row — so every run of `recreate_ogcr_entities.sh` ends with exactly those rows present.

Currently fixtured:
- **`technologies_practices_processes`** — the 28 technologies/practices/processes an activity can declare. Ids are `UPPERCASE_WITH_UNDERSCORES` and the label is derived from the id in proper case, with acronyms in `fixtures.ACRONYMS` left uppercase (`GEOLOGICAL_CO2_STORAGE` → `Geological CO2 Storage`, `..._BECCS` → `... BECCS`).
- **`country`** — all 249 ISO 3166-1 alpha-2 codes, in `iso_3166_1_countries.py`. The id is the two-letter code (`DE`) and the label is the ISO English **short name** (`Germany`). A handful read formally (`Korea, Republic of`, `Taiwan, Province of China`); each carries a `# commonly:` comment if you prefer the common name. The module header has the one-liner that regenerates it from the system `iso-codes` package.
- **`sustainable_development_goal`** — the 17 UN Sustainable Development Goals, in `sustainable_development_goals.py`, transcribed from the "SDGs enum" sheet of `SDG_enum.xlsx`. The id is e.g. `NO_POVERTY`, the label `No Poverty`, and the goal's icon URL goes in `sustainable_development_goal_link`. The goal number (`GOAL_1`) is carried as `sustainable_development_goal_number`, which the entity does not define yet, so it is skipped with a warning until that field is added to the sheet.

How a fixture is written:
- The id goes in `<entity>_id`. OBP preserves a supplied `<entity>_id`, so these codes are the stable keys other records reference.
- The label goes in the entity's name field, resolved per entity by `fixtures.resolve_name_field`: `name`, else `<entity>_name`, else the sheet's only other `*_name` field (this is how `technologies_practices_processes.practice_name` is found). If the sheet has several `*_name` fields the choice is ambiguous, so ids are written without a label and a warning is logged.
- Extra fields given in an `(id, label, {field: value})` row are written as-is when the sheet declares that field, and skipped with a warning when it does not.
- Any *other* field the sheet declares for that entity keeps its spreadsheet example and declared type.
- Rows already stored are skipped, so the script is safe to re-run against a populated instance.
- Stored rows that are *not* in the fixture list are logged as a warning and left in place (a full recreate wipes them anyway).

Topping up an existing instance:

```bash
python3 create_dummy_data.py --fixtures-only     # writes only the fixtured entities
```

`--fixtures-only` skips every non-fixtured entity, so it will not duplicate (or error on) the single example rows those already have. Combined with the skip-if-present behaviour, it is the way to add newly defined fixture values, or to retry rows that failed, without a full wipe-and-recreate.

> **Id length:** the `<entity>_id` column is a `varchar` whose width is set by the OBP deployment, so the ceiling is instance-specific. An id that exceeds it is rejected with `OBP-50015 ... value too long for type character varying(N)`. The OBP default has been `varchar(36)`; this project's instance was widened to `varchar(255)`. If you hit the error against a narrower instance, shorten the id — the display name is independent, so use the `(id, name)` form to keep the full wording — rather than assuming every instance has the wider column.

To add a value, add it to the list in `fixtures.py`. To fixture another entity, add an `entity_name: [rows]` pair to `FIXTURES`, where a row is either a bare id (label derived), an explicit `(id, label)` pair, or an `(id, label, {field: value})` triple for extra fields.

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
1. Ensure env vars set (or a `.env` file present), then check login: `./check_login_and_roles.sh --no-entities`.
2. Check the spreadsheet: `./check_min_field_matrix.sh`.
3. Inspect parsing output:

```bash
python3 parse_minimum_fields.py
```

4. Create entities on OBP (confirm with `--yes` or interactively):

```bash
python3 parse_minimum_fields.py --create --yes
```

5. Grant and check the Roles: `./create_entitlements.sh` then `./check_login_and_roles.sh`.

6. Use `main.py` to clean and recreate system entities defined in `dynamic_entities.py`:

```bash
python3 main.py
```

**Where to look for issues**
- Parsed entities printed by `parse_minimum_fields.py` show the exact `value` and `example` used to build the dynamic entity schema.
- If a field example must be a number, ensure column H contains an unquoted numeric value (the parser will coerce when possible).

If you want me to add example `.env` content, a quick test script, or adjust any parsing detail, tell me which part to update next.

**Funding**

The OGCR Project has received funding from the European Union's Horizon Europe programme under grant agreement 101218854.


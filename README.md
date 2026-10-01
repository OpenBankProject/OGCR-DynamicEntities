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
- **`create_role_groups.py`** / **`.sh`**: Create or update the OBP Groups defined by the spreadsheet's Role Group matrix (columns R onwards).
- **`add_users_to_groups.py`** / **`.sh`**: Add users to those groups, as ticked in `DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx`.
- **`sync_user_group_permissions.py`** / **`.sh`**: Bring one user's group memberships (added and removed, as ticked in that sheet) and Roles (in every group they are in) up to date.
- **`show_user_dynamic_entity_roles.py`** / **`.sh`**, **`show_user_dynamic_entity_paths.py`** / **`.sh`**, **`grant_user_dynamic_entity_roles.py`** / **`.sh`**: Look at, or grant, one user's dynamic entity Roles (see "One user's dynamic entity Roles").
- **`diff_entities.py`** / **`.sh`**: Show how the dynamic entities on OBP, at the space's bank id (or `--bank-id`), differ from the spreadsheet: entities and fields only on one side, and per field the type, required, indexed, description and example (`--structure-only` skips the last two). Read-only; exits 1 when they differ.
- **`role_groups.py`**: Reads that matrix (offline; used by the checker and `create_role_groups.py`).
- **`dynamic_resource_docs.py`**, **`recreate_dynamic_resource_docs.sh`**: Manage the Dynamic Resource Docs (e.g. the public registry endpoint, `registry_activities_endpoint.scala`). The `.sh` compiles, deletes, recreates and checks each doc (step 6 of `recreate_dynamic_entities.sh`); `--dry-run` only compiles them and lists what is on OBP.
- **`dry_run_recreate_dynamic_entities.py`** / **`.sh`**: DRY RUN of `recreate_dynamic_entities.sh` — says what it would do, changes nothing.
- **`create_space_bank.py`** / **`.sh`**: Create the `OBP_ENTITY_SPACE_ID` bank if it doesn't exist.
- **`obp_space.py`**: The one place that builds dynamic-entity URLs and Role bank ids from `OBP_ENTITY_SPACE_ID`.

**Where the entities live (`OBP_ENTITY_SPACE_ID`)**

All OGCR entities live in one place: either at system level, or under one bank (OBP also calls a bank a *Space*). Set `OBP_ENTITY_SPACE_ID` in `.env` to choose; unset, it is `ogcr`, the same default as OGCR-App and OGCR-chain-cache:

| `OBP_ENTITY_SPACE_ID` | Definitions | Records | Roles granted at bank id |
|---|---|---|---|
| empty | `/obp/<v>/management/system-dynamic-entities` | `/obp/dynamic-entity/[public/]<entity>` | `SYS` |
| `ogcr` (default) | `/obp/<v>/management/banks/ogcr/dynamic-entities` | `/obp/dynamic-entity/banks/ogcr/[public/]<entity>` | `ogcr` |

Every script (create, update, delete, dummy data, Roles, join indexes, audit log) builds its URLs from `obp_space.py`, so they always agree, and deleting only ever touches entities in the configured space. This replaces the old `OBP_ENTITY_PREFIX`, which has been removed.

The bank must exist before entities can be created in it. `recreate_dynamic_entities.sh` creates it if it's missing, or run it on its own:

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
- A `number` field's example is always sent as a decimal (`6` → `6.0`). OBP's generated API docs (OpenAPI) take each field's type from its example, so a whole number would document the field as an integer; and the sheet can't carry the `.0`, because Excel stores `6.0` as `6` and pandas reads it back as an integer.

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
- example in column G that does not fit its type (integer, number, boolean, `DATE_WITH_DAY`, json)
- a Role Group cell that isn't made of the letters `C R U D`, or two groups with the same name

Possible warnings it can report:
- no `END_OF_FILE` row in column A
- ticked field with an empty type
- field name changed by sanitising (e.g. `monitoring period` → `monitoring_period`)
- type in the wrong case (e.g. `Integer`)
- Role Group access on a field row instead of the `Entity:` row (ignored), in lower case, or with a repeated letter

The output lists only the problems actually found (`ERRORS FOUND` / `WARNINGS FOUND`). Exit code: `0` no errors, `1` errors (or warnings with `--strict`). `recreate_dynamic_entities.sh` runs it first and stops on any error, before anything on OBP is deleted.

**Re-create the entities (delete then create from the spreadsheet)**

**Preview it first with a DRY RUN.** `./dry_run_recreate_dynamic_entities.sh [path/to/min_field_matrix.xlsx]` walks the same steps as `recreate_dynamic_entities.sh` in the same space, but only reads (the sheet, and GET requests to OBP). Every line starts with `[DRY RUN]`, and it reports: problems in the sheet; whether the space's bank would be created; each entity it would delete, with its record count; entities in the space it would leave alone; each entity it would create; the example data; the Roles `create_entitlements.sh` would still need to grant; then the Role Groups it would create or update, and the users it would add to them; and last, whether the Dynamic Resource Docs compile, and which are on OBP now. It doesn't rewrite `entities_output.txt`. Pass `--only` to preview just the entities.

`recreate_dynamic_entities.sh` itself starts by showing the host, the space (`OBP_ENTITY_SPACE_ID`) and the sheet, and asks you to type `yes` before it changes anything. Pass `--yes` to skip the question in automation; without a terminal and without `--yes` it stops.

After the entities and example data, it also runs `create_role_groups.py` (step 4), `add_users_to_groups.py` (step 5, only if `DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx` exists) and finally `recreate_dynamic_resource_docs.sh` (step 6); see "Role Groups" below. A failure in step 4 stops the run. A user who can't be added in step 5 (e.g. not on this OBP), or a resource doc that can't be recreated in step 6, is reported, the rest still run, and the script exits 1 at the end. Pass `--only` to recreate only the entities and skip those three steps:

```bash
./recreate_dynamic_entities.sh                 # entities, example data, Role Groups, users, resource docs
./recreate_dynamic_entities.sh --only          # entities and example data only
```

To see what takes a while: each step prints `⏱ <step>: <seconds>`, and a table of all the step times and the total is printed at the end, also when a step fails. Inside steps 1–3, each entity's delete, create, reference restore and example data gets its own `⏱` line if it takes over 1s, and each of those scripts ends with its 5 slowest operations. The example data timings would include writing the audit log records, but `recreate_dynamic_entities.sh` doesn't turn the audit log on (see `--log` below).

Each run also writes a complete log to `logs/recreate_dynamic_entities_<date>-<time>.log`: everything printed on the console (errors included), plus every timing, including the ones under 1s that the console leaves out. It starts with a header giving the host, space, sheet, git commit and options, so it can be handed as-is to someone, or an agent, looking into the dynamic entities. The path is printed at the start and end of the run. `logs/` is git-ignored, because step 5 can write real usernames into it.

A clean wipe-and-recreate driven entirely by the spreadsheet (this is what `main.py` does *not* do — `main.py` is tied to the hardcoded list in `dynamic_entities.py`):

1. **Parse and save** the entity list to `entities_output.txt`:

```bash
python3 parse_minimum_fields.py min_field_matrix.xlsx --save   # non-interactive
# or run without --save and answer "y" at the prompt (default filename entities_output.txt)
```

2. **Delete** those entities and all their records on OBP with `delete_dynamic_entities.py`:

```bash
python3 delete_dynamic_entities.py            # reads entities_output.txt by default; prompts for confirmation
python3 delete_dynamic_entities.py --yes      # skip the confirmation prompt
```

3. **Re-create** the entities from the spreadsheet:

```bash
python3 parse_minimum_fields.py min_field_matrix.xlsx --create --yes
```

Notes:
- `delete_dynamic_entities.py` deletes exactly the entities listed in `entities_output.txt` (one per `Entity:` line) and leaves all other dynamic entities on the instance untouched. If an entity was **renamed** in the spreadsheet, the old name is *not* in the file and will be left on OBP as an orphan — delete it separately. To wipe **every** dynamic entity instead, use `delete_all_dynamic_entities.py`.
- Deletion runs in repeated passes so reference (foreign-key) constraints between entities don't block a clean delete, and it exits non-zero if anything it was asked to delete survives.
- Always regenerate `entities_output.txt` (step 1) after editing the spreadsheet, so the delete list matches what you are about to create.
- `delete_dynamic_entities.py` options: `file` (positional, default `entities_output.txt`), `--yes` (skip confirmation), `--token` (override the DirectLogin token).

**Roles (`check_login_and_roles.sh`, `create_entitlements.sh`)**

Every entity needs Roles, all granted at the bank id of the space (`OBP_ENTITY_SPACE_ID`, or `SYS` for system level):
- definition Roles: `CanCreateDynamicEntityDefinition`, `CanDeleteDynamicEntityDefinition`, `CanGetDynamicEntityDefinitions`, `CanUpdateDynamicEntityDefinition`
- record Roles, per entity: `CanCreateDynamicEntityRecord_<entity>`, and the same for `Delete`, `Get` and `Update`
- Role Group Roles, for steps 4 and 5 of `recreate_dynamic_entities.sh`: `CanCreateGroupAtOneBank`, `CanUpdateGroupAtOneBank`, `CanGetGroupsAtOneBank`, `CanAddUserToGroupAtOneBank`, `CanRemoveUserFromGroupAtOneBank`; plus `CanGetEntitlementsForAnyBank`, `CanGetAnyUser` and `CanDeleteEntitlementAtAnyBank` at system level (empty bank id)

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

Roles the user already holds are skipped (it reads the current user's entitlements first) and only the missing ones are requested; it lists what it granted and exits 1 if any grant failed. A record Role can only be granted once its entity exists on OBP (otherwise `400 Unknown role`), so run this after creating the entities. Granting Roles itself needs `CanCreateEntitlementAtAnyBank` (or `CanCreateEntitlementAtOneBank` at the space's bank id).

**One user's dynamic entity Roles**

Three scripts for any user, named by their username. That's the user you look at or grant to, not the one logged in from `.env`. Add `--provider` if the username exists at more than one provider.

```bash
./show_user_dynamic_entity_roles.sh lantonic                  # their dynamic entity entitlements at the space's bank id (OBP_ENTITY_SPACE_ID)
./show_user_dynamic_entity_roles.sh lantonic --bank-id SYS    # ... or at another bank id (SYS includes the empty bank id)
./show_user_dynamic_entity_roles.sh lantonic --by-entity      # one line per entity, with its access as C R U D letters
./show_user_dynamic_entity_paths.sh lantonic                  # every record path those Roles open
./grant_user_dynamic_entity_roles.sh lantonic --entity parcel --entity activity           # CRUD at the space's bank id
./grant_user_dynamic_entity_roles.sh lantonic --entity supporting_document --access R --bank-id ogcr --dry-run
```

Each Role is marked with the group that granted it, or `NOT through a group` (granted by hand, by an entitlement request, or by a group since deleted). Removing a user from their groups leaves those, so they may still be able to call the endpoints. `add_users_to_groups.sh` and `sync_user_group_permissions.sh` list them too, at every bank id. Seeing which group granted what needs `CanGetUserGroupMembershipsAtOneBank` (or `...AtAllBanks`).

`show_user_dynamic_entity_paths.sh` prints one path per line. The v7.0.0 paths come first (`/obp/v7.0.0/banks/BANK_ID/dynamic-entities/ENTITY[/ID]`, banks such as `ogcr` first, then `SYS`), then the legacy ones (`/obp/dynamic-entity/[banks/BANK_ID/]ENTITY[/ID]`). A path to an entity that isn't defined in its space is marked `404`.

`grant_user_dynamic_entity_roles.sh` takes the entities with `--entity` (repeat it), and the Roles as the letters `C R U D`, like the Role Group matrix (`--access`, default `CRUD`), at `--bank-id` (default: the space's bank id, `OBP_ENTITY_SPACE_ID`, or `SYS` for system level). It grants only the Roles the user doesn't already hold at that bank id. It lists them and asks before granting, because the user gets an email for each one; `--dry-run` only lists them.

The show scripts only read, and need `CanGetAnyUser`. Checking that entities exist also needs `CanGetDynamicEntityDefinitions` at their bank id. Granting needs `CanCreateEntitlementAtAnyBank`.

**Role Groups (`create_role_groups.sh`)**

The spreadsheet's first sheet has a Role Group matrix, starting at column R and running right until the first empty header. Row 1 holds each group's name (R1 = `Operator`, S1 = `Certification Scheme`, T1 = `Certification Body`, U1 = `Parcel Owner Verifier`). Where a group's column crosses an `Entity: <name>` row, the letters say which of that entity's record endpoints the group may call:

| Letter | Endpoints | Role |
|---|---|---|
| `C` | POST | `CanCreateDynamicEntityRecord_<entity>` |
| `R` | GET list and GET one | `CanGetDynamicEntityRecord_<entity>` |
| `U` | PUT | `CanUpdateDynamicEntityRecord_<entity>` |
| `D` | DELETE | `CanDeleteDynamicEntityRecord_<entity>` |

Any combination works (`R`, `CR`, `CRUD`, ...); empty means no access. Only the `Entity:` rows count; `check_min_field_matrix.sh` flags anything else.

`create_role_groups.sh` makes each column an OBP Group (`/obp/v6.0.0/management/groups`) with those Roles, plus `CanGetDynamicEntityDefinitions` in every group so any member can list the entity definitions, at the bank id of the space (`OBP_ENTITY_SPACE_ID`, or `SYS` for system level) — the same bank id the Roles are checked at. A group that already exists there with the same name has its Roles replaced by the sheet's; other groups are left alone.

```bash
./create_role_groups.sh --dry-run      # say what would be created / updated
./create_role_groups.sh                # do it
./create_role_groups.sh --user simonredfern --dry-run   # bring only this user up to date
```

Add users to a group with `POST /obp/v6.0.0/users/USER_ID/group-entitlements` (`{"group_id": "..."}`), which grants them the group's Roles. OBP copies the Roles at the moment a user is added, so a changed group doesn't change its existing members. The script therefore has OBP update each group's members in place, without taking them out of the group (`POST /obp/v7.0.0/management/groups/GROUP_ID/sync-members`). A Role of the group that a member doesn't hold in any way is granted to them. A Role taken out of the group has the member's entitlement for it, granted by this group, deleted, unless another group the member is in still grants it: then it's kept, and recorded against that group. Members whose Roles already match are left alone. Users get an email for each entitlement granted, so this sends only one per Role that is actually new to them. `--dry-run` lists each member that would be updated, and the Roles, judged against the group's Roles as they are on OBP now (the group itself isn't updated in a dry run). OBP records group memberships, so a member who got nothing from a group because other groups had already given them its Roles is still updated.

With `--user USERNAME` (and `--provider` if the username is at more than one provider) the groups are still created and updated from the sheet, but only that user is brought up to date (`POST /obp/v7.0.0/management/users/USER_ID/sync-groups`), in every group they are in, at any bank id. The other members are left as they are until a run without `--user`. It also clears the user's entitlements left by groups that have since been deleted (deleting a group leaves them in place): each is moved to another of their groups that grants the Role, or deleted.

**Adding users to the groups (`add_users_to_groups.sh`)**

Who is in which group is kept in `DO_NOT_COMMIT/Users-Group-DO_NOT_COMMIT.xlsx`, sheet `Users-Groups-DO_NOT_COMMIT`. It holds real usernames, so `DO_NOT_COMMIT/` and any `*DO_NOT_COMMIT*` file are git-ignored. Row 1: `Username` (A), `Provider` (B), then one column per group from C (named exactly like the groups). Tick `TRUE` under each group a user should be in.

```bash
./add_users_to_groups.sh --dry-run            # say who would be added where
./add_users_to_groups.sh                      # do it
./add_users_to_groups.sh --user some.username # just one row
```

Each user is looked up by username (`GET /obp/v6.0.0/users?username=`), and by provider too when column B is filled in. Fill it in if the same username exists at more than one provider; the script says so. Users already in a group are left alone. Nobody is removed: a user who is in a group but not ticked for it is only reported (`sync_user_group_permissions.sh` below removes them, for one user). Unknown users, and group columns with no matching OBP Group, are reported, and the script exits 1. Needs `CanGetAnyUser`, `CanGetUserGroupMembershipsAtOneBank` and `CanAddUserToGroupAtOneBank` at the space's bank id.

**Syncing one user (`sync_user_group_permissions.sh`)**

When a user's ticks in the users sheet change, or their groups' Roles have changed on OBP:

```bash
./sync_user_group_permissions.sh --user some.username --dry-run
./sync_user_group_permissions.sh --user some.username
```

Step 1 is `add_users_to_groups.py --user USERNAME --remove-unticked`: added to the groups ticked for them, and removed from the sheet's groups they aren't ticked for (`DELETE /obp/v6.0.0/users/USER_ID/group-entitlements/GROUP_ID`). Removing deletes the entitlements that group granted them, except a Role another of their groups still grants. Additions are made first, so a Role a newly ticked group also grants is kept rather than deleted and granted again. Needs `CanRemoveUserFromGroupAtOneBank` as well. Step 2 brings their Roles in line with every group they are in, at any bank id (`POST /obp/v7.0.0/management/users/USER_ID/sync-groups`), and clears entitlements left by groups since deleted. The groups' Roles are taken as they are on OBP; to change them from the Role Group matrix first, run `create_role_groups.sh` (with `--user some.username` to bring only this user up to date). In a dry run, step 2 is previewed against the groups the user is in now, before step 1's changes.

The groups don't depend on the entities existing. `recreate_dynamic_entities.sh` runs both scripts after recreating the entities, unless given `--only`. Needs `CanCreateGroupAtOneBank`, `CanUpdateGroupAtOneBank` and `CanGetGroupsAtOneBank` at the space's bank id (or the `...AtAllBanks` versions); updating members also needs `CanAddUserToGroupAtOneBank` and `CanRemoveUserFromGroupAtOneBank` (all granted by `create_entitlements.sh`).

**Create dummy data**

`create_dummy_data.py` creates one sample object per entity, driven by the same spreadsheet. Run it *after* the entities exist on OBP (see "Re-create the entities" above):

```bash
python3 create_dummy_data.py [path/to/min_field_matrix.xlsx] [--token TOKEN]
```

- **`file`** (positional): spreadsheet path. Defaults to `min_field_matrix.xlsx`.
- **`--token`**: DirectLogin token (overrides the token from `obp_client.py`).
- **`--log`**: Write the audit trail to the `ogcr_dynamicentities_log` dynamic entity. Off by default; `recreate_dynamic_entities.sh` doesn't pass it.

How it works:
- **Values come from the spreadsheet** — each field is populated from its column G `example` value, coerced to the field's declared type (string, `integer`, `number`, `boolean`, `json`, `DATE_WITH_DAY`).
- **Foreign keys are made valid** — any `<entity>_id` field is overwritten with the real id of the referenced object, so the dummy data is referentially consistent (e.g. `activity.operator_id` points at the created `operator`, and `audit_report` links to the operator, activity, scheme, body, plans and certificate).
- Entities that own an `<entity>_id` field get a canonical id taken from the spreadsheet example; the verification/report entities without one receive an OBP-generated UUID.
- The field `compliance_certificate_id` (which does not follow the `<entity>_id` convention) is mapped to `certificate_of_compliance` via an explicit alias in the script (`FK_ALIASES`).

- **The run can be audited in OBP** — off by default. Only when `--log` is given does the script ensure a dynamic entity named after this application, `ogcr_dynamicentities_log` (in the same space as the other entities), exists (defined in `dummy_data_creation_log_helpers.py`) and write one record to it per object: `entity_created` for each created object and `entity_failed` for each failed create (with the OBP error text). Each record carries `entity_name`, `entity_id`, `status`, `message`, a UTC `timestamp`, and a json `references` list describing **every** `reference:<x>` field on the entity and how it resolved — each item has `field`, `target`, `resolution` (`resolved` = a real created id was used; `fallback` = the spreadsheet example value was used because the target is a static OBP entity or one we don't create here) and the `value` posted. Logging is best-effort: if the log entity cannot be created or a record fails to POST, the data creation continues uninterrupted.

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

Some entities are not examples but fixed lists of values the rest of the system selects from. These live in `fixtures.py`, not in the spreadsheet, and `create_dummy_data.py` writes the whole list instead of a single example row — so every run of `recreate_dynamic_entities.sh` ends with exactly those rows present.

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


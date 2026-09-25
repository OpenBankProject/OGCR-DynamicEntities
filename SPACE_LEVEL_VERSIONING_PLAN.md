# Space (bank) level Dynamic Entities as a versioning mechanism — plan

**Status:** the scripts side (§4.1, §6.1) is implemented as of 2026-09-25: `OBP_ENTITY_SPACE_ID`
and `obp_space.py`, with `create_space_bank.py` creating the bank if it is missing.
`OBP_ENTITY_PREFIX` was removed from this repo, which settles risk 2 in favour of spaces.
§7 is out of date: record Roles are now `Can<Action>DynamicEntityRecord_<entity>` at every
level, granted at the bank id (`SYS` for system level), so the name no longer changes.
The OGCR-App side (§4.2, §6.2) is not done.
**Written:** 2026-09-21. **Verified against:** `http://localhost:8080` (OBP, dynamic entity API v5.1.0).

The idea: use an OBP **bank — aka Space** — as a namespace for a *version* of the OGCR
schema, so `/banks/ogcr_v1/...` and `/banks/ogcr_v2/...` can hold the same entity names
with different definitions and separate rows, side by side.

**Space rule (decided):** an OGCR deployment is **either** entirely system-level
**or** entirely bank-level. No per-entity mixing — one switch, one URL shape.

---

## 1. What was verified

Probed with throwaway entities on the local instance (all deleted afterwards). These
are facts about this OBP build, not assumptions:

| Question | Result |
|---|---|
| Same entity name, **different schema**, at two banks | ✅ both `201` |
| Rows isolated per bank | ✅ a v2-only field existed only at the second bank |
| Same name *also* at system level, concurrently | ✅ all three coexist |
| `reference:` between two bank-level entities in one bank | ✅ kept, not downgraded |
| `reference:` from a **bank** entity to a **system** entity | ✅ kept, and enforced (invalid FK → `400`) |
| Public read at bank level | ✅ works — see the path warning below |

Cross-level references are recorded for completeness; the all-or-nothing space rule
means we don't rely on them.

### The path rule

All four dynamic-entity paths follow one pattern:

```
/obp/dynamic-entity/[banks/BANK_ID/][public/]ENTITY
```

| | Authenticated | Public |
|---|---|---|
| System | `/obp/dynamic-entity/ENTITY` | `/obp/dynamic-entity/public/ENTITY` |
| Space | `/obp/dynamic-entity/banks/BANK_ID/ENTITY` | `/obp/dynamic-entity/banks/BANK_ID/public/ENTITY` |

The space prefix comes first; `public` always sits immediately before the entity name.

Worth knowing when implementing the path builder: a malformed variant such as
`/obp/dynamic-entity/public/banks/BANK_ID/ENTITY` returns `404`, which is
indistinguishable from "entity missing" or "public access off" — so a URL bug there
will look like a data or permissions problem.

## 2. Model

Every OGCR entity — domain entities *and* the reference vocabularies `country` and
`technologies_practices_processes` — lives at the configured space:

| Configuration | Entity path | Public read path |
|---|---|---|
| System (today) | `/obp/dynamic-entity/ENTITY` | `/obp/dynamic-entity/public/ENTITY` |
| Bank | `/obp/dynamic-entity/banks/BANK_ID/ENTITY` | `/obp/dynamic-entity/banks/BANK_ID/public/ENTITY` |

Consumers migrate between versions by changing one path segment; old and new stay
live in parallel.

Consequence of the space rule: each version carries **its own copy** of the
vocabularies (249 countries, 28 practices) at its own public URL. That is cheap to
create — `create_dummy_data.py --fixtures-only` populates them — but it means the
open-data URL is version-specific by design, not stable across versions.

## 3. ⚠️ Naming collision to resolve first

**OGCR-App already uses `bank_id` to mean something else.**
`src/lib/obp/currentBank.ts` stores a *user-selected* bank as the OBP user attribute
`CURRENT_BANK_ID`, deliberately shared with OBP Portal and API Manager, and used by
`/trading`. If a "version bank" were read from the same place, a user changing banks
in the picker would silently change which *schema version* they see.

**Therefore:** the entity space is a configuration-level value that is never the
user's current bank. That drives the env var naming below — do **not** call it
`OBP_BANK_ID`.

## 3.1 Why "space" and not an invented word

OBP already uses **Space as an alias for Bank**, so the terminology is borrowed rather
than coined. Evidence in `OBP-API-Simon/OBP-API`:

| Source | Shows |
|---|---|
| `code/model/dataAccess/AuthUser.scala:976` | *"If a User creates a Bank (aka Space) the user can create and modify Dynamic Endpoints and other objects in that Bank / Space."* |
| `code/api/v4_0_0/JSONFactory4.0.0.scala:709` | `case class MySpaces(bank_ids: List[String])` — a Space **is** a bank id |
| `code/api/v4_0_0/Http4s400.scala:3818` | `GET /my/spaces` — the alias is already on the API surface |
| `props/sample.props.template:1608` | *"the bank_ids (Spaces) the User has access to"*, prop `email_domain_to_space_mappings` |

So `OBP_ENTITY_SPACE_ID` reads naturally to anyone who knows OBP, avoids the
`CURRENT_BANK_ID` collision in §3, and matches the direction of travel if the URL
segment gains a `spaces` alias (§5).

## 4. Environment variables

One variable, the same name in both repos, and the values must agree.

### 4.1 OGCR-DynamicEntities (this repo, `.env`)

| Variable | Default | Meaning |
|---|---|---|
| `OBP_ENTITY_SPACE_ID` | *(empty)* | The bank id owning this deployment's entities, e.g. `ogcr_v2`. **Empty = system level = today's behaviour.** Single switch; unsetting it is the rollback. |

The URL segment (`banks`, later `spaces` — §5) is a **constant in the path builder, not
configuration**: it is the same on every instance, so making it an env var would only
create a way for two deployments to disagree.

`OBP_ENTITY_PREFIX` stays as it is — see risk 1.

> The value **is** an OBP bank id; `SPACE` is OBP's own alias for it (§3.1), chosen
> here because it is unambiguous against the user-selected `CURRENT_BANK_ID`.

### 4.2 OGCR-App-Simon (`OGCR-App/.env` and `.env.example`)

| Variable | Scope | Default | Meaning |
|---|---|---|---|
| `OBP_ENTITY_SPACE_ID` | private (`$env/dynamic/private`) | *(empty)* | Must match the scripts' value for the version being served. **Not** the user's `CURRENT_BANK_ID`. |
| `PUBLIC_OBP_ENTITY_SPACE_ID` | public | *(omit initially)* | Only if the **browser** ever builds a dynamic-entity URL itself. All current access is server-side, so leave it out until a page needs it. |

Follow the repo's existing convention: private vars via `$env/dynamic/private`
(as `src/lib/constants/entities.ts` already does for `OBP_ENTITY_PREFIX`), `PUBLIC_`
only for what the client must see. Add it to `.env.example` with a comment — that
file is the de-facto deployment documentation.

## 5. The URL segment: ask OBP for a fixed `spaces` alias

OBP currently hardcodes `banks` in both the data and management paths:

```
data:        /obp/dynamic-entity/banks/BANK_ID/ENTITY
management:  /obp/v5.1.0/management/banks/BANK_ID/dynamic-entities
```

To make the OGCR API surface less banky, the ask is a **fixed alias accepted on every
instance** — `spaces` (optionally `s` as a shorthand) routing to the same handlers —
**not** a per-deployment configurable segment.

A configurable segment would make every URL deployment-specific: shared client code,
examples, docs and cross-instance scripts would all need parameterising, and two OBP
instances would stop speaking the same URL language. A fixed alias gets the same
cosmetic result with none of that, and it finishes an alias OBP has already started
(`GET /my/spaces`, the `email_domain_to_space_mappings` prop, "Bank (aka Space)" in
`AuthUser.scala` — see §3.1).

Consequently the segment is a **constant in each repo's path builder**, not an
environment variable. Switching from `banks` to `spaces` once OBP accepts it is a
one-line code change in two places, applied together.

If the alias is added, it should cover both the data and management paths, so the two
builders stay consistent.

## 6. Code changes required

### 6.1 This repo

| File | Change |
|---|---|
| `obp_dynamic_api.py` | One path builder used everywhere: management URL becomes `/management/banks/<id>/dynamic-entities` when a space is set; same for update/delete by id. Note this is a genuine branch, not a prefix — the system form uses a different noun (`system-dynamic-entities`). |
| `create_dummy_data.py` | Object paths become `/obp/dynamic-entity/banks/<id>/<entity>` — a pure prefix; `existing_object_ids` too. |
| `parse_minimum_fields.py` | Thread the space through both create passes and `--update`. |
| `delete_ogcr_entities.py`, `get_and_delete_dynamic_entities.py` | List and delete within the space only — must never touch another version's entities. |
| `add_join_indexes.py` | Fetch/PUT definitions within the space. |
| `create_entitlements.py` | Grant **bank-level** roles (§7) — currently system-only. |
| `recreate_ogcr_entities.sh` | Pass the space through; refuse to run if the bank doesn't exist, so a version is never half-created. |

Because the space is all-or-nothing, every one of these is the same mechanical edit:
replace a hardcoded path with the shared builder. No per-entity branching anywhere.

### 6.2 OGCR-App

| File | Change |
|---|---|
| `src/lib/constants/entities.ts` | Add `dynamicEntityPath(entity)` returning the system or space path. Single chokepoint, alongside the existing `ENTITY_PREFIX` logic. |
| ~30 call sites of `/obp/dynamic-entity/...` across `src/routes/**` and `src/lib/**` | Replace hand-built paths with the helper. Mechanical but wide. |
| `src/lib/server/roleChecker.ts`, `src/lib/utils/roleCheck.ts` | Role names differ at bank level (§7); derive from the configured space rather than hardcoding `_System`. |
| `src/lib/obp/currentBank.ts` | **No change** — must stay independent. Worth a comment saying so, to stop a future reader wiring them together. |
| `.env`, `.env.example` | Add the vars from §4.2. |

## 7. Entitlements

Bank-level roles drop `System` and are held **at the bank**:

| Level | Role name |
|---|---|
| System | `CanGetDynamicEntity_System<entity>` |
| Bank | `CanGetDynamicEntity_<entity>`, granted at `BANK_ID` |

Consequence: **every version bank needs its own grants for every user and entity.**
With N entities and M versions that is N × M grants per user. `create_entitlements.py`
must loop over spaces, and onboarding a user to a new version becomes an explicit
step. This is the largest recurring operational cost of the approach.

**There is a precedent worth asking OBP to extend.** The `email_domain_to_space_mappings`
prop already auto-grants roles per space: a user whose validated email domain maps to a
set of `bank_ids` is granted the roles for those spaces on login and on DirectLogin
token generation (`AuthUser.scala:1010-1013`). Today it covers **Dynamic Endpoint**
roles only — `listOfRolesToUseAllDynamicEndpointsAOneBank` reads from
`DynamicEndpointProvider` (`DynamicEndpointHelper.scala:169`), not from dynamic
entities. Extending the same mechanism to Dynamic Entity roles would remove most of
the sprawl above, and is a small, well-precedented OBP change to request.

Note the path segment (§5) does not change role names — they are not path-derived.

## 8. Risks and open questions

1. **A dropped prefix reads different data, silently.** The space prefix does not
   scope a shared resource — it selects a *different entity that happens to share a
   name*, with its own schema and rows (§1 confirms three same-named entities can be
   live at once). So:

   | Mistake | Result |
   |---|---|
   | Malformed path | `404` — loud |
   | Prefix dropped entirely | `200` with another version's data — **silent** |

   Every OGCR entity is system-level today. If a space is adopted and the system-level
   entities are left in place, any un-migrated call site keeps working while quietly
   reading v1. Mitigations: (a) **delete the system-level entities after cutover**, so
   a dropped prefix 404s; (b) assert on the response envelope — space responses carry
   `"bank_id": "<id>"`, system responses carry no such key, so the app's path helper
   can verify which namespace actually answered.

2. **Two namespacing mechanisms.** `OBP_ENTITY_PREFIX` already exists and is wired
   through both repos. Prefix *and* space would be two ways to say the same thing.
   Decide which owns versioning; document the other as not-for-that-purpose.
3. **Entitlement sprawl** (§7).
4. **No automatic data migration.** A new version starts empty. Vocabularies are
   trivial (re-run the fixtures), but operator/activity/parcel rows need an explicit,
   written copy step — including how in-flight records are handled.
5. **No cross-version references.** A v2 `activity` cannot reference a v1 `parcel`.
   Usually desirable; confirm it doesn't break a real workflow.
6. **Semantic overloading of "bank"** (§3), plus unknown interactions with consents,
   scopes and bank-scoped OBP tooling. Untested. The §5 rename reduces the cosmetic
   part of this, not the underlying one.
7. **Public open-data URLs become version-specific** (§2). Accept, or publish a stable
   alias outside OBP.
8. **Chain/tokenizer side.** `OGCR-chain-cache` and the tokenizer also read OBP
   entities and inherit the same path and role changes. Not scoped here.

## 9. Rollout (if adopted)

1. **Decide** §3 naming and risk 1.
2. **Scripts first, behind the env var.** With `OBP_ENTITY_SPACE_ID` empty, behaviour
   is byte-for-byte what it is today — verify that before going further.
3. **Create the version bank** and grant entitlements (§7).
4. **Populate** the space: entities from the spreadsheet, then
   `create_dummy_data.py --fixtures-only` for the vocabularies.
5. **App:** path helper + role names + env, still defaulting to system level.
6. **Cut over** one environment by setting `OBP_ENTITY_SPACE_ID` in both repos.
   **Rollback = unset it.**

## 10. Alternatives considered

| Option | Verdict |
|---|---|
| **Additive schema evolution** — only add optional fields, update in place via `--update` | Far less work; no new concepts. **Preferred unless concurrent schemas are genuinely required.** Does not help when a field must change type or be removed. |
| **`OBP_ENTITY_PREFIX` per version** (`v2_operator`) | The mechanism already exists in both repos — the cheapest real versioning available today, and no OBP change needed. Pollutes the entity catalogue and role list. Worth comparing seriously before committing to spaces. |
| **Entity name suffix** (`country_v2`) | Same as above without the prefix plumbing; every consumer hardcodes the version in the entity name. |
| **Version field on rows** | Solves data versioning, not schema versioning. Not applicable. |

## 11. Decision needed

The deciding question is narrow: **do old and new schemas need to be live at the same
time, with consumers migrating at their own pace?**

- **Yes** → space-level entities, as specified above. The evidence in §1 says it works.
- **No** → additive evolution through the existing `--update` path; revisit later.

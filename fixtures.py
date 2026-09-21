"""Controlled vocabularies that must exist on every run.

The spreadsheet drives the entity *definitions* plus one example record each
(see `create_dummy_data.py`). A few entities are not examples at all: they are
fixed lists of values the rest of the system selects from. Those belong here,
in code, so every run of `create_dummy_data.py` (and therefore every run of
`recreate_ogcr_entities.sh`) ends with exactly these rows in the table.

A fixture is a list of rows for one entity. A row is either:
  * a bare id string - the display name is derived from it in proper case
    (`COVER_CROPPING` -> `Cover Cropping`), for vocabularies we coin ourselves,
    where the convention is UPPERCASE_WITH_UNDERSCORES; or
  * an `(id, name)` pair - for external code lists such as ISO 3166-1, where
    the name cannot be derived from the code (`DE` -> `Germany`).
"""

from iso_3166_1_countries import COUNTRIES

# Acronyms that must not be title-cased when deriving a name from an id.
ACRONYMS = {"DACS", "BECCS", "CO2"}


def proper_case_name(fixture_id):
    """`COVER_CROPPING` -> `Cover Cropping`, `GEOLOGICAL_CO2_STORAGE` -> `Geological CO2 Storage`."""
    return " ".join(
        word if word in ACRONYMS else word.capitalize()
        for word in fixture_id.split("_")
    )


# The technologies, practices and processes an activity can declare.
TECHNOLOGIES_PRACTICES_PROCESSES_IDS = [
    "COVER_CROPPING",
    "CATCH_CROPS",
    "NO_TILL",
    "MINIMUM_TILLAGE",
    "PRECISION_FERTILIZATION",
    "RESIDUE_MANAGEMENT",
    "AGROFORESTRY",
    "OTHER_MIXED_FARMING",
    "CROPLAND_TO_FALLOW",
    "SET_ASIDE_TO_PERMANENT_GRASSLAND_CONVERSION",
    "PEATLAND_RESTORATION",
    "WETLAND_RESTORATION",
    "PEATLAND_REWETTING",
    "WETLAND_REWETTING",
    "CONTINUOUS_COVER_FORESTRY",
    "SUSTAINABLE_FOREST_MANAGEMENT",
    "AFFORESTATION",
    "REFORESTATION",
    "ENHANCED_ROCK_WEATHERING",
    "LANDSCAPE_FEATURE_ENHANCEMENT",
    "DIRECT_AIR_CAPTURE_WITH_STORAGE_DACS",
    "BIOCHAR_PRODUCTION_AND_APPLICATION",
    "BIOGENIC_EMISSIONS_CAPTURE",
    "BIOENERGY_WITH_CARBON_CAPTURE_AND_STORAGE_BECCS",
    "GEOLOGICAL_CO2_STORAGE",
    "WOOD_BASED_CONSTRUCTION_PRODUCTS",
    "BIO_BASED_CONSTRUCTION_PRODUCTS",
    "OTHER_PERMANENTLY_CHEMICALLY_BOUND_CARBON_IN_PRODUCTS",
]

# entity name -> ordered list of rows (bare ids, or explicit (id, name) pairs).
FIXTURES = {
    "technologies_practices_processes": TECHNOLOGIES_PRACTICES_PROCESSES_IDS,
    # ISO 3166-1 alpha-2 is the code OGCR uses for every country reference.
    "country": COUNTRIES,
}

# Preferred names for the field holding a row's human-readable label, most
# specific first. `country` calls it `country_name`; other entities may use
# `name` or something of their own (see resolve_name_field).
NAME_FIELDS = ("name", "{entity}_name")


def resolve_name_field(entity_name, sheet_fields):
    """The field a fixture row's display name belongs in, or None if there isn't one.

    Prefers `name` / `<entity>_name`. Otherwise falls back to the sheet's only
    other `*_name` field (e.g. `technologies_practices_processes.practice_name`),
    since a fixture row is just an id plus a label; if the sheet has several,
    the choice is ambiguous and the caller writes ids only.
    """
    for candidate in (f.format(entity=entity_name) for f in NAME_FIELDS):
        if candidate in sheet_fields:
            return candidate
    others = sorted(f for f in sheet_fields if f.endswith("_name"))
    return others[0] if len(others) == 1 else None


def fixture_records(entity_name):
    """`[(id, name), ...]` for `entity_name`, or `[]` when it has no fixture."""
    rows = []
    for row in FIXTURES.get(entity_name, []):
        if isinstance(row, (tuple, list)):
            rows.append((row[0], row[1]))
        else:
            rows.append((row, proper_case_name(row)))
    return rows

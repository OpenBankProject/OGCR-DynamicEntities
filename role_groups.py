"""Read the Role Group matrix from the minimum fields spreadsheet (min_field_matrix.xlsx).

Columns R onwards of the first sheet, up to the first empty header, are Role
Groups: row 1 holds the group's name (e.g. R1 = Operator), and the cell where a
group's column crosses an `Entity: <name>` row says which of that entity's
record endpoints the group may call:

    C  create  -> CanCreateDynamicEntityRecord_<entity>
    R  read    -> CanGetDynamicEntityRecord_<entity>     (GET list and GET one)
    U  update  -> CanUpdateDynamicEntityRecord_<entity>
    D  delete  -> CanDeleteDynamicEntityRecord_<entity>

Any combination may be written (R, CR, CRUD, ...); empty means no access. Cells
on field rows are ignored: access is per entity, not per field.

No side effects on import (no login), so offline scripts can use it too.
"""

import re

import pandas as pd

END_MARKER = "END_OF_FILE"
# Column R. The sheet says not to move columns, so the matrix starts here.
FIRST_GROUP_COLUMN = 17

ROLE_PREFIX_BY_LETTER = {
	"C": "CanCreateDynamicEntityRecord_",
	"R": "CanGetDynamicEntityRecord_",
	"U": "CanUpdateDynamicEntityRecord_",
	"D": "CanDeleteDynamicEntityRecord_",
}
ACCESS_ORDER = "CRUD"


def column_letter(idx):
	"""0-based column index -> Excel letter(s), e.g. 17 -> R."""
	letters = ""
	idx += 1
	while idx:
		idx, rem = divmod(idx - 1, 26)
		letters = chr(ord("A") + rem) + letters
	return letters


def roles_for(entity_name, access):
	"""Role names for `access` (e.g. 'CRUD') on one entity, in C R U D order."""
	return [ROLE_PREFIX_BY_LETTER[c] + entity_name for c in ACCESS_ORDER if c in access]


def _group_columns(df):
	"""[(index, name)] of the group columns: from R, until the first empty header.
	pandas names an empty header 'Unnamed: N'."""
	columns = []
	for idx in range(FIRST_GROUP_COLUMN, len(df.columns)):
		header = str(df.columns[idx]).strip()
		if not header or header.startswith("Unnamed:"):
			break
		columns.append((idx, header))
	return columns


def parse_role_groups(file_path):
	"""Return (groups, errors, warnings).

	groups is a list of {"name", "column", "access": {entity: "CRUD"-subset}}, in
	sheet order. Each problem is a string starting with its Excel cell. Cells that
	are errors are left out of `access`.
	"""
	df = pd.read_excel(file_path, engine="openpyxl")
	errors, warnings = [], []
	columns = _group_columns(df)
	groups = [{"name": name, "column": column_letter(idx), "access": {}} for idx, name in columns]

	seen_names = {}
	for group in groups:
		if group["name"] in seen_names:
			errors.append(f"{group['column']}1: group {group['name']!r} is already defined at "
				f"{seen_names[group['name']]}1")
		seen_names.setdefault(group["name"], group["column"])

	current = None
	for index, row in df.iterrows():
		excel_row = index + 2  # header is row 1
		col_a = "" if pd.isna(row.iloc[0]) else str(row.iloc[0]).strip()
		if col_a == END_MARKER:
			break
		is_entity_row = col_a.lower().startswith("entity:")
		if is_entity_row:
			current = col_a[7:].strip()

		for (idx, _), group in zip(columns, groups):
			value = row.iloc[idx]
			if pd.isna(value) or not str(value).strip():
				continue
			cell = f"{group['column']}{excel_row}"
			raw = str(value).strip()
			if not is_entity_row:
				warnings.append(f"{cell}: {raw!r} for group {group['name']!r} is not on an `Entity:` row "
					"(ignored; access is set per entity)")
				continue
			letters = re.sub(r"\s+", "", raw)
			if not re.fullmatch(r"[CRUDcrud]+", letters):
				errors.append(f"{cell}: {raw!r} for group {group['name']!r} on {current} "
					"may only contain the letters C R U D (ignored)")
				continue
			if letters != letters.upper():
				warnings.append(f"{cell}: {raw!r} for group {group['name']!r} on {current} "
					f"should be written {letters.upper()!r}")
			letters = letters.upper()
			if len(set(letters)) != len(letters):
				warnings.append(f"{cell}: {raw!r} for group {group['name']!r} on {current} repeats a letter")
			group["access"][current] = "".join(c for c in ACCESS_ORDER if c in letters)

	return groups, errors, warnings


def group_roles(group):
	"""All the Role names of one parsed group, entity by entity."""
	return [role for entity, access in group["access"].items() for role in roles_for(entity, access)]

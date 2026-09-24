from dynamic_entities import entities_data, add_entitlement_to_user
from obp_client import token

#TODO: call get current_user
user_id = "9e564728-48fc-4ce4-97ae-417889746959"
# The Roles that gate an entity's DEFINITION. These keep their old names and are still granted at the
# empty bank id; they join the Record Roles below when the system level management endpoints gain a
# space in their URL.
meta_role_names = [
	"CanCreateSystemLevelDynamicEntity",
	"CanDeleteSystemLevelDynamicEntity",
	"CanGetSystemLevelDynamicEntities",
	"CanUpdateSystemLevelDynamicEntity"
	]
# The Roles that gate an entity's RECORDS. They were renamed on 2026-09-24: the "_System" variant is
# gone, because the Role no longer says which space it applies to -- the bank id of the grant does.
# For a system level entity that bank id is the literal SYS, not the empty string.
role_names = [
	"CanCreateDynamicEntityRecord_",
	"CanDeleteDynamicEntityRecord_",
	"CanGetDynamicEntityRecord_",
	"CanUpdateDynamicEntityRecord_"
	]
system_space_bank_id = "SYS"
for m in meta_role_names:
	add_entitlement_to_user(
		token=token,
		user_id=user_id,
		role_name=m)

for i in entities_data:
	for r in role_names:
		print(r + i[0])
		add_entitlement_to_user(
			token=token,
			user_id=user_id,
			role_name=r + i[0],
			bank_id=system_space_bank_id)
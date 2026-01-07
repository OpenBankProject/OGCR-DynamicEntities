from dynamic_entities import entities_data, add_entitlement_to_user
from obp_client import token

user_id = "db2b67d7-f30f-4b8a-bb31-749b977e597b"
meta_role_names = [
	"CanCreateSystemLevelDynamicEntity",
	"CanDeleteSystemLevelDynamicEntity",
	"CanGetSystemLevelDynamicEntities",
	"CanUpdateSystemLevelDynamicEntity"
	]
role_names = [
	"CanCreateDynamicEntity_System",
	"CanDeleteDynamicEntity_System",
	"CanGetDynamicEntity_System",
	"CanUpdateDynamicEntity_System"
	]
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
			role_name=r + i[0])
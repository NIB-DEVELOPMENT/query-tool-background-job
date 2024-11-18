select sr.display_name
from dbo.security_role_user sru
inner join dbo.security_role sr on sr.role_id = sru.role_id
where sru.security_users_id = :user_id
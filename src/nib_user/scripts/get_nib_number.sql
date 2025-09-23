select p.alt_identifier
from dbo.security_users su
inner join dbo.person p on p.person_id = su.person_id
where su.security_users_id = :user_id
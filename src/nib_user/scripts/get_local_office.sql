select su.security_users_id,
(select max(f.lookup_value_03)
from dbo.factor_definition fd
inner join dbo.factor f on fd.factor_id = f.factor_id and f.lookup_value_02 = su.user_type
where fd.factor_name = 'LOCAL_OFFICE_CODES'
) local_office
from dbo.security_users su
where su.security_users_id = :user_id
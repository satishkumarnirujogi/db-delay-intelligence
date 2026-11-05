-- Run once in Supabase → SQL Editor AFTER replacing the password below.
-- Do NOT commit the real password: replace it only inside the SQL Editor.
create role powerbi_reader login password 'CHANGE-ME-strong-password';
grant usage on schema marts, ml, ops to powerbi_reader;
grant select on all tables in schema marts, ml, ops to powerbi_reader;
alter default privileges in schema marts grant select on tables to powerbi_reader;
alter default privileges in schema ml    grant select on tables to powerbi_reader;
alter default privileges in schema ops   grant select on tables to powerbi_reader;
-- Through the Session pooler this user logs in as: powerbi_reader.<project-ref>

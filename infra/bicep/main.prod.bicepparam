using 'main.bicep'

param environment = 'prod'
param location = 'southafricanorth'
param projectPrefix = 'ipacgs'

// Prod should use a real group, not an individual account — smaller,
// more tightly controlled membership than dev/test's shortcut. Explicit
// here rather than relying on main.bicep's User default.
param platformAdminObjectId = '00000000-0000-0000-0000-000000000000'
param platformAdminPrincipalType = 'Group'

param postgresAdminLogin = 'ipacgsadmin'
// Read from the environment, not hardcoded — see main.dev.bicepparam's note
// on why this can't be a separate --parameters CLI override (BCP258).
// Source this from a dedicated prod secret store, not the same value as
// dev/test's POSTGRES_ADMIN_PASSWORD.
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD')

param apiImageTag = 'placeholder'

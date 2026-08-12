using 'main.bicep'

param environment = 'dev'
param location = 'southafricanorth'
param projectPrefix = 'ipacgs'

// Replace with a real Entra ID object ID before deploying — see
// infra/README.md § First deployment. Defaults to your own account
// (platformAdminPrincipalType = 'User' in main.bicep) so this works without
// Groups Administrator rights; switch both params if/when a real
// platform-admins group exists.
param platformAdminObjectId = '00000000-0000-0000-0000-000000000000'

param postgresAdminLogin = 'ipacgsadmin'
// Read from the environment at deploy time, not hardcoded — .bicepparam
// files are validated as a complete, self-contained set of parameters, so
// a separate `--parameters postgresAdminPassword=...` CLI override does NOT
// merge with this file the way a classic JSON parameters file would
// (BCP258 if you try). Export POSTGRES_ADMIN_PASSWORD before deploying.
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD')

param apiImageTag = 'placeholder'

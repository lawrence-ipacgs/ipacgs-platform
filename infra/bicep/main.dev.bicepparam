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
// postgresAdminPassword is intentionally NOT set here — pass it at deploy
// time: --parameters postgresAdminPassword=$POSTGRES_ADMIN_PASSWORD

param apiImageTag = 'placeholder'

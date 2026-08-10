using 'main.bicep'

param environment = 'dev'
param location = 'southafricanorth'
param projectPrefix = 'ipacgs'

// Replace with the real Entra ID object ID for the platform-admins group
// before deploying — see infra/README.md § First deployment.
param platformAdminObjectId = '00000000-0000-0000-0000-000000000000'

param postgresAdminLogin = 'ipacgsadmin'
// postgresAdminPassword is intentionally NOT set here — pass it at deploy
// time: --parameters postgresAdminPassword=$POSTGRES_ADMIN_PASSWORD

param apiImageTag = 'placeholder'

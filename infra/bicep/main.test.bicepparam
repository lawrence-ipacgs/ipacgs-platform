using 'main.bicep'

param environment = 'test'
param location = 'southafricanorth'
param projectPrefix = 'ipacgs'

// See main.dev.bicepparam's note — defaults to your own account (User),
// no admin rights required.
param platformAdminObjectId = '00000000-0000-0000-0000-000000000000'

param postgresAdminLogin = 'ipacgsadmin'
// Read from the environment, not hardcoded — see main.dev.bicepparam's note
// on why this can't be a separate --parameters CLI override (BCP258).
// Use a different POSTGRES_ADMIN_PASSWORD value than dev's for this env.
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD')

param apiImageTag = 'placeholder'

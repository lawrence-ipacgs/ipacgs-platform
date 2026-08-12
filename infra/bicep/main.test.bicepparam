using 'main.bicep'

param environment = 'test'
param location = 'southafricanorth'
param projectPrefix = 'ipacgs'

// See main.dev.bicepparam's note — defaults to your own account (User),
// no admin rights required.
param platformAdminObjectId = '00000000-0000-0000-0000-000000000000'

param postgresAdminLogin = 'ipacgsadmin'
// postgresAdminPassword passed at deploy time — see main.dev.bicepparam's note.

param apiImageTag = 'placeholder'

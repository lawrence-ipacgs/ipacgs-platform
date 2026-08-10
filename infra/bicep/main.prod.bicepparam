using 'main.bicep'

param environment = 'prod'
param location = 'southafricanorth'
param projectPrefix = 'ipacgs'

// Prod platform-admin group should be smaller and more tightly controlled
// than dev/test's — confirm membership before first deploy.
param platformAdminObjectId = '00000000-0000-0000-0000-000000000000'

param postgresAdminLogin = 'ipacgsadmin'
// postgresAdminPassword passed at deploy time, from a dedicated prod secret
// store (not the same value as dev/test) — see main.dev.bicepparam's note.

param apiImageTag = 'placeholder'

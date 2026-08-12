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
// postgresAdminPassword passed at deploy time, from a dedicated prod secret
// store (not the same value as dev/test) — see main.dev.bicepparam's note.

param apiImageTag = 'placeholder'

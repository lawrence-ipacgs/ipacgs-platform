using 'main.bicep'

param environment = 'dev'
param location = 'southafricanorth'
param projectPrefix = 'ipacgs'

// Lawrence's own object ID (az ad signed-in-user show) — the account that
// ran the original Epic 0 deploy. Committed rather than left as a
// placeholder for a local edit: the first deploy used a real value that
// only ever existed as an uncommitted Cloud Shell edit, which a later
// `git pull` silently reverted to the placeholder and broke a redeploy
// (PrincipalNotFound on an all-zero GUID) — not a secret, just an
// object ID, so there's no reason not to check it in. Switch both this
// and platformAdminPrincipalType (main.bicep) if/when a real
// platform-admins group replaces a single named admin.
param platformAdminObjectId = '5a8af707-9fd3-45d1-ace9-45d0b9fab3f9'

param postgresAdminLogin = 'ipacgsadmin'
// Read from the environment at deploy time, not hardcoded — .bicepparam
// files are validated as a complete, self-contained set of parameters, so
// a separate `--parameters postgresAdminPassword=...` CLI override does NOT
// merge with this file the way a classic JSON parameters file would
// (BCP258 if you try). Export POSTGRES_ADMIN_PASSWORD before deploying.
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD')

param apiImageTag = 'placeholder'

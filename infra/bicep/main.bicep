// IPAC Governance Systems — Epic 0: Platform Foundation
// Subscription-scope orchestrator: creates the environment's resource group,
// then deploys every foundation resource into it.
//
// Nothing here has been applied yet. Review, then deploy with e.g.:
//   az deployment sub create \
//     --location southafricanorth \
//     --template-file main.bicep \
//     --parameters main.dev.bicepparam
//
// FR/ARCH references: ARCH-003, DEV-CICD-001, FR-IAM-001…004, NFR-SEC-003,
// FR-MDM-001…002 — see the Epic 0 ticket list in the architecture document.

targetScope = 'subscription'

@description('Environment name — dev, test or prod. Drives resource naming and sizing.')
@allowed(['dev', 'test', 'prod'])
param environment string

@description('Primary Azure region. South Africa North by default — change per data-residency requirements.')
param location string = 'southafricanorth'

@description('Short project prefix used in every resource name.')
param projectPrefix string = 'ipacgs'

@description('Object ID of the Entra ID user or group that receives initial Key Vault + data admin access. Required — no default, so a real value must be supplied per environment.')
param platformAdminObjectId string

@description('Whether platformAdminObjectId is a User or a Group. Defaults to User — your own account, no Groups Administrator role required — since a group can be introduced later without touching anything downstream of this parameter.')
@allowed(['User', 'Group'])
param platformAdminPrincipalType string = 'User'

@description('Postgres administrator login name.')
param postgresAdminLogin string = 'ipacgsadmin'

@secure()
@description('Postgres administrator password. Pass via --parameters postgresAdminPassword=$POSTGRES_ADMIN_PASSWORD at deploy time — never commit it.')
param postgresAdminPassword string

@description('Container image tag to deploy for the API. Defaults to a placeholder until the first image is published.')
param apiImageTag string = 'placeholder'

var resourceGroupName = 'rg-${projectPrefix}-${environment}'
var tags = {
  project: 'ipacgs'
  environment: environment
  milestone: '1.1'
  managedBy: 'bicep'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module foundation 'modules/foundation.bicep' = {
  name: 'foundation-${environment}'
  scope: rg
  params: {
    environment: environment
    location: location
    projectPrefix: projectPrefix
    tags: tags
    platformAdminObjectId: platformAdminObjectId
    platformAdminPrincipalType: platformAdminPrincipalType
    postgresAdminLogin: postgresAdminLogin
    postgresAdminPassword: postgresAdminPassword
    apiImageTag: apiImageTag
  }
}

output resourceGroupName string = rg.name
output postgresFqdn string = foundation.outputs.postgresFqdn
output keyVaultUri string = foundation.outputs.keyVaultUri
output storageAccountName string = foundation.outputs.storageAccountName
output containerRegistryLoginServer string = foundation.outputs.containerRegistryLoginServer
output apiFqdn string = foundation.outputs.apiFqdn

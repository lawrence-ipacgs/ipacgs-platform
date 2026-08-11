// Resource-group-scope composition of every Epic 0 resource.
// Deployed by ../main.bicep — not meant to be deployed standalone.
param environment string
param location string
param projectPrefix string
param tags object
param platformAdminObjectId string
param platformAdminPrincipalType string
param postgresAdminLogin string

@secure()
param postgresAdminPassword string
param apiImageTag string

module logAnalytics 'log-analytics.bicep' = {
  name: 'log-analytics'
  params: {
    location: location
    projectPrefix: projectPrefix
    environment: environment
    tags: tags
  }
}

module keyVault 'keyvault.bicep' = {
  name: 'key-vault'
  params: {
    location: location
    projectPrefix: projectPrefix
    environment: environment
    tags: tags
    platformAdminObjectId: platformAdminObjectId
    platformAdminPrincipalType: platformAdminPrincipalType
    workspaceId: logAnalytics.outputs.workspaceId
  }
}

module storage 'storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    projectPrefix: projectPrefix
    environment: environment
    tags: tags
    workspaceId: logAnalytics.outputs.workspaceId
  }
}

module postgres 'postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    projectPrefix: projectPrefix
    environment: environment
    tags: tags
    administratorLogin: postgresAdminLogin
    administratorPassword: postgresAdminPassword
    workspaceId: logAnalytics.outputs.workspaceId
  }
}

module registry 'container-registry.bicep' = {
  name: 'container-registry'
  params: {
    location: location
    projectPrefix: projectPrefix
    environment: environment
    tags: tags
  }
}

module containerApps 'container-apps.bicep' = {
  name: 'container-apps'
  params: {
    location: location
    projectPrefix: projectPrefix
    environment: environment
    tags: tags
    workspaceCustomerId: logAnalytics.outputs.workspaceCustomerId
    workspaceSharedKey: logAnalytics.outputs.workspaceSharedKey
    registryLoginServer: registry.outputs.loginServer
    registryName: registry.outputs.registryName
    keyVaultName: keyVault.outputs.vaultName
    keyVaultUri: keyVault.outputs.vaultUri
    apiImageTag: apiImageTag
  }
}

// Runtime secrets (DB password, storage connection string, etc.) are
// deliberately NOT created here. They're set post-deploy via
// `az keyvault secret set` or the CI/CD pipeline's release step — see
// infra/README.md § Secrets. Keeping real secret values out of Bicep means
// re-running a deployment never risks overwriting a rotated secret with a
// stale one baked into source control.

output postgresFqdn string = postgres.outputs.fqdn
output keyVaultUri string = keyVault.outputs.vaultUri
output storageAccountName string = storage.outputs.storageAccountName
output containerRegistryLoginServer string = registry.outputs.loginServer
output apiFqdn string = containerApps.outputs.apiFqdn

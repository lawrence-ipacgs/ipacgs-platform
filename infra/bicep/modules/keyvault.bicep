// Secrets management — NFR-SEC-003.
// RBAC-based access (not legacy access policies) so grants are auditable
// through the same Entra ID role assignments as everything else.
param location string
param projectPrefix string
param environment string
param tags object
param platformAdminObjectId string
param workspaceId string

// Key Vault names are globally unique and capped at 24 chars.
var vaultName = take('kv-${projectPrefix}-${environment}', 24)

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: environment == 'prod' ? true : null
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

// "Key Vault Administrator" built-in role — full data-plane control for the
// platform admin group. Application services get narrower "Key Vault Secrets
// User" assignments added when each service's managed identity is created.
resource adminRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, platformAdminObjectId, 'KeyVaultAdministrator')
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00482a5a-887f-4fb3-b363-3b7fe8e74483')
    principalId: platformAdminObjectId
    principalType: 'Group'
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${vaultName}'
  scope: vault
  properties: {
    workspaceId: workspaceId
    logs: [
      { category: 'AuditEvent', enabled: true }
    ]
  }
}

output vaultName string = vault.name
output vaultUri string = vault.properties.vaultUri
output vaultId string = vault.id

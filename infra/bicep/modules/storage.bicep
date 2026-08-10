// Evidence vault — Layer 2 (Master data & evidence). Blob storage holding
// every uploaded evidence document, versioned, private by default.
param location string
param projectPrefix string
param environment string
param tags object
param workspaceId string

// Storage account names: globally unique, lowercase alphanumeric, <=24 chars.
var storageAccountName = take(toLower('st${projectPrefix}${environment}${uniqueString(resourceGroup().id)}'), 24)

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: { name: environment == 'prod' ? 'Standard_GRS' : 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
    isVersioningEnabled: true // FR-EVD-003 — every evidence upload is versioned
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 30 }
    containerDeleteRetentionPolicy: { enabled: true, days: 30 }
  }
}

resource evidenceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'evidence-vault'
  properties: { publicAccess: 'None' }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${storageAccountName}'
  scope: blobService
  properties: {
    workspaceId: workspaceId
    logs: [
      { category: 'StorageRead', enabled: true }
      { category: 'StorageWrite', enabled: true }
      { category: 'StorageDelete', enabled: true }
    ]
  }
}

output storageAccountName string = storage.name
output storageAccountId string = storage.id
output evidenceContainerName string = evidenceContainer.name

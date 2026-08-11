// Observability foundation — every other module logs here.
param location string
param projectPrefix string
param environment string
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${projectPrefix}-${environment}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: environment == 'prod' ? 90 : 30
  }
}

output workspaceId string = workspace.id
output workspaceName string = workspace.name
output workspaceCustomerId string = workspace.properties.customerId

// Computed here, against the resource this module declares natively, rather
// than via a cross-module `existing` lookup keyed on another module's output
// — that pattern hits BCP307 (Bicep can't resolve listKeys() against an
// `existing` resource whose name is itself only known after deployment).
@secure()
output workspaceSharedKey string = workspace.listKeys().primarySharedKey

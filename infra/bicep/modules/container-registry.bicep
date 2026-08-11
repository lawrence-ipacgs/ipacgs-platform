// Holds the API's container images between CI build and Container Apps deploy.
param location string
// minLength constraints here (not just relying on main.bicep's own) are what
// let Bicep prove registryName can't fall below ACR's 5-char minimum —
// without them the linter has to assume both could be empty.
@minLength(3)
param projectPrefix string
@minLength(3)
param environment string
param tags object

var registryName = take(toLower('cr${projectPrefix}${environment}'), 24)

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: registryName
  location: location
  tags: tags
  sku: { name: environment == 'prod' ? 'Premium' : 'Basic' }
  properties: {
    adminUserEnabled: false // CI/CD authenticates via managed identity, not admin keys
  }
}

output loginServer string = registry.properties.loginServer
output registryId string = registry.id
output registryName string = registry.name

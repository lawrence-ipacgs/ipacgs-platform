// Compute for the API — Container Apps environment + the API container app
// itself, running under its own managed identity (no secrets in the image,
// no admin keys — pulls from ACR and reads Key Vault by identity).
param location string
param projectPrefix string
param environment string
param tags object
param workspaceId string
param workspaceCustomerId string
@secure()
param workspaceSharedKey string
param registryLoginServer string
param registryId string
param keyVaultId string
param keyVaultUri string
param apiImageTag string

var envName = 'cae-${projectPrefix}-${environment}'
var appName = 'ca-${projectPrefix}-api-${environment}'
var identityName = 'id-${projectPrefix}-api-${environment}'

resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

// AcrPull — lets the API's identity pull its own image without admin keys.
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registryId, apiIdentity.id, 'AcrPull')
  scope: resourceId('Microsoft.ContainerRegistry/registries', split(registryId, '/')[8])
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User — read-only secret access, no vault management.
resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultId, apiIdentity.id, 'KeyVaultSecretsUser')
  scope: resourceId('Microsoft.KeyVault/vaults', split(keyVaultId, '/')[8])
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspaceCustomerId
        sharedKey: workspaceSharedKey
      }
    }
  }
}

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${apiIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
      registries: [
        {
          server: registryLoginServer
          identity: apiIdentity.id
        }
      ]
      secrets: [
        {
          name: 'key-vault-uri'
          value: keyVaultUri
        }
      ]
    }
    template: {
      containers: [
        {
          // Placeholder image until CI publishes the first real build —
          // swap for '${registryLoginServer}/ipacgs-api:${apiImageTag}'
          // once services/api has an image to push.
          image: apiImageTag == 'placeholder' ? 'mcr.microsoft.com/k8se/quickstart:latest' : '${registryLoginServer}/ipacgs-api:${apiImageTag}'
          name: 'api'
          env: [
            { name: 'ENVIRONMENT', value: environment }
            { name: 'KEY_VAULT_URI', secretRef: 'key-vault-uri' }
            { name: 'AZURE_CLIENT_ID', value: apiIdentity.properties.clientId }
          ]
          resources: {
            cpu: json(environment == 'prod' ? '1.0' : '0.5')
            memory: environment == 'prod' ? '2Gi' : '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: environment == 'prod' ? 2 : 0
        maxReplicas: environment == 'prod' ? 10 : 3
      }
    }
  }
}

output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output apiIdentityPrincipalId string = apiIdentity.properties.principalId
output apiIdentityClientId string = apiIdentity.properties.clientId

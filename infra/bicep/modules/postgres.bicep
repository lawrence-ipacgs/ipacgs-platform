// Master data store — Layer 2. Azure Database for PostgreSQL Flexible Server,
// holding Tenant / Organisation / Person·Party and everything built on top.
param location string
param projectPrefix string
param environment string
param tags object
param administratorLogin string

@secure()
param administratorPassword string
param workspaceId string

var serverName = 'psql-${projectPrefix}-${environment}'
var skuName = environment == 'prod' ? 'Standard_D2ds_v4' : 'Standard_B1ms'
var skuTier = environment == 'prod' ? 'GeneralPurpose' : 'Burstable'
var storageSizeGb = environment == 'prod' ? 128 : 32
var haEnabled = environment == 'prod'

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: serverName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    storage: { storageSizeGB: storageSizeGb }
    backup: {
      backupRetentionDays: environment == 'prod' ? 35 : 7
      geoRedundantBackup: environment == 'prod' ? 'Enabled' : 'Disabled'
    }
    highAvailability: {
      mode: haEnabled ? 'ZoneRedundant' : 'Disabled'
    }
    network: {
      // Public access with firewall rules for now — tighten to VNet
      // injection before prod handles real evidence.
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource allowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: server
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource ipacgsDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: server
  name: 'ipacgs'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${serverName}'
  scope: server
  properties: {
    workspaceId: workspaceId
    logs: [
      { category: 'PostgreSQLLogs', enabled: true }
    ]
  }
}

output fqdn string = server.properties.fullyQualifiedDomainName
output serverName string = server.name
output databaseName string = ipacgsDatabase.name

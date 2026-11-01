// VISION DEV demo on Azure App Service (Linux). PREPARED ONLY: nothing here has been deployed.
// Synthetic data only. Authentication (Entra / App Service Authentication) is owned by IT and
// is intentionally not configured here; access is denied by default until allowed CIDRs are given.
targetScope = 'resourceGroup'

@description('Globally unique web app name, e.g. vision-dev-<suffix>.')
param webAppName string

@description('Region approved by IT.')
param location string = resourceGroup().location

@description('App Service plan SKU. B1 supports WebSockets and Always On; F1 does not.')
@allowed(['B1', 'B2'])
param skuName string = 'B1'

@description('IPv4 CIDR ranges allowed to reach the app (e.g. corporate egress/VPN). Required: no default, so nothing is public by accident.')
@minLength(1)
param allowedCidrs array

@description('Python runtime supported by the plan; verify with: az webapp list-runtimes --os linux')
param pythonVersion string = '3.13'

@description('Log Analytics retention in days (30 is the minimum for pay-as-you-go workspaces).')
@minValue(30)
param logRetentionDays int = 30

@description('Daily Log Analytics ingestion cap in GB (decimal string), to bound cost.')
param dailyLogCapGb string = '0.2'

var tags = {
  application: 'vision'
  environment: 'dev'
  data: 'synthetic-only'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${webAppName}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: logRetentionDays
    workspaceCapping: { dailyQuotaGb: json(dailyLogCapGb) }
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${webAppName}-plan'
  location: location
  tags: tags
  kind: 'linux'
  sku: { name: skuName }
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'PYTHON|${pythonVersion}'
      appCommandLine: 'bash deploy/azure/startup.sh'
      alwaysOn: true
      webSocketsEnabled: true
      http20Enabled: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      healthCheckPath: '/_stcore/health'
      ipSecurityRestrictionsDefaultAction: 'Deny'
      scmIpSecurityRestrictionsDefaultAction: 'Deny'
      // SCM/Kudu is the deployment endpoint. Reuse the same approved network allowlist.
      // The deploy runner must therefore execute inside an allowed corporate/VPN egress range.
      scmIpSecurityRestrictionsUseMain: true
      ipSecurityRestrictions: [for (cidr, i) in allowedCidrs: {
        name: 'allow-${i}'
        priority: 100 + i
        action: 'Allow'
        ipAddress: cidr
      }]
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'CO_VISION_DATA_ROOT', value: '/tmp/co-vision-dev-data' }
      ]
    }
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'to-log-analytics'
  scope: app
  properties: {
    workspaceId: logs.id
    logs: [
      { category: 'AppServiceHTTPLogs', enabled: true }
      { category: 'AppServiceConsoleLogs', enabled: true }
    ]
  }
}

output defaultHostName string = app.properties.defaultHostName
output principalId string = app.identity.principalId

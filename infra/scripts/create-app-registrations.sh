#!/usr/bin/env bash
# Entra ID app registrations for IPACGS — FR-IAM-001…004.
#
# NOT executed by CI or by anything else in this repo. Review each command,
# then run by hand (or paste into an Azure Cloud Shell) once you're ready to
# wire up identity for a given environment. Re-running is safe — `az ad app
# create` on a name that already exists just creates a second app, so check
# `az ad app list --display-name` first if you're not sure whether this has
# already been run for the environment you're targeting.
set -euo pipefail

ENVIRONMENT="${1:?Usage: create-app-registrations.sh <dev|test|prod>}"

echo "== Creating API app registration (ipacgs-api-${ENVIRONMENT}) =="
API_APP_ID=$(az ad app create \
  --display-name "ipacgs-api-${ENVIRONMENT}" \
  --sign-in-audience AzureADMyOrg \
  --query appId -o tsv)
echo "API app registered: ${API_APP_ID}"

echo "== Creating web app registration (ipacgs-web-${ENVIRONMENT}) =="
WEB_APP_ID=$(az ad app create \
  --display-name "ipacgs-web-${ENVIRONMENT}" \
  --sign-in-audience AzureADMyOrg \
  --web-redirect-uris "https://ipacgs-web-${ENVIRONMENT}.azurewebsites.net/api/auth/callback" \
  --query appId -o tsv)
echo "Web app registered: ${WEB_APP_ID}"

cat <<EOF

Next steps (manual — role definitions belong in version control, not a
throwaway CLI session):

1. Add App Roles on the API app registration matching the SRS role model
   (Section 4 — Project Sponsor/Owner, Assurance Lead/Assessor, Independent
   Reviewer/Approver, etc.) via the Azure Portal or 'az ad app update
   --app-roles @roles.json'. Keep roles.json in this repo once written —
   don't hand-edit only in the portal, or the next environment's setup drifts.

2. Grant the web app registration API permissions to call the API app
   registration's custom scopes (expose an API on ${API_APP_ID} first).

3. Record both app IDs in Key Vault, not in code:
   az keyvault secret set --vault-name kv-ipacgs-${ENVIRONMENT} \\
     --name api-app-client-id --value ${API_APP_ID}
   az keyvault secret set --vault-name kv-ipacgs-${ENVIRONMENT} \\
     --name web-app-client-id --value ${WEB_APP_ID}

4. FR-IAM-004 (maker-checker segregation) is enforced in application logic
   against these roles, not by Entra ID itself — see
   services/api/src/ipacgs/core/security.py once that's built out past the
   current stub.
EOF

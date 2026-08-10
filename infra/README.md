# Infrastructure — Epic 0: Platform Foundation

Bicep, deployed at subscription scope. Nothing in here has been applied to
Azure yet — this is infrastructure-as-code for review, not a record of what's
live. `az` isn't installed in the environment this was written in; the notes
below assume you're running from a machine (or Cloud Shell) that has it.

## What gets created, per environment

| Resource | Purpose | Module |
|---|---|---|
| Resource group `rg-ipacgs-{env}` | Isolation boundary between dev/test/prod | `main.bicep` |
| Log Analytics workspace | Every other resource's diagnostic destination | `log-analytics.bicep` |
| Key Vault (RBAC-mode) | Secrets — `NFR-SEC-003` | `keyvault.bicep` |
| Storage account, `evidence-vault` container | Evidence documents, versioned — `FR-EVD-003` | `storage.bicep` |
| PostgreSQL Flexible Server, `ipacgs` database | Master data — `FR-MDM-001…002` | `postgres.bicep` |
| Container Registry | Holds the API's built images | `container-registry.bicep` |
| Container Apps environment + API app | Runs the API under its own managed identity | `container-apps.bicep` |

Naming convention: `{resource-type-abbrev}-ipacgs-{env}` (storage/registry/vault
names drop the dashes where Azure requires it). Region defaults to
`southafricanorth`; override via the `location` parameter if data residency
requirements point elsewhere.

## First deployment (dev)

1. **Install and authenticate Azure CLI**, if you haven't:
   ```bash
   brew install azure-cli   # or: https://aka.ms/installazurecliwindows / apt/dnf for Linux
   az login
   az account set --subscription "<your subscription name or ID>"
   ```

2. **Get the platform-admin Entra ID group's object ID** and put it in
   `main.dev.bicepparam` in place of the placeholder GUID:
   ```bash
   az ad group show --group "IPACGS Platform Admins" --query id -o tsv
   ```
   If that group doesn't exist yet, create it first (`az ad group create`) —
   don't point this at an individual's object ID; it should be a group so
   membership can change without a redeploy.

3. **Generate a Postgres admin password** and keep it somewhere real (a
   password manager, not a note) — you'll need it again for the connection
   string in step 5:
   ```bash
   POSTGRES_ADMIN_PASSWORD=$(openssl rand -base64 24)
   ```

4. **Validate before deploying:**
   ```bash
   az deployment sub what-if \
     --location southafricanorth \
     --template-file main.bicep \
     --parameters main.dev.bicepparam \
     --parameters postgresAdminPassword=$POSTGRES_ADMIN_PASSWORD
   ```

5. **Deploy:**
   ```bash
   az deployment sub create \
     --location southafricanorth \
     --template-file main.bicep \
     --parameters main.dev.bicepparam \
     --parameters postgresAdminPassword=$POSTGRES_ADMIN_PASSWORD
   ```

## Secrets

Bicep creates the Key Vault; it does **not** populate it with real secret
values — a redeploy should never risk overwriting a rotated secret with a
stale one baked into source control. After the first deploy, set the
connection string by hand (or via the CI/CD release step once that's wired up):

```bash
az keyvault secret set \
  --vault-name kv-ipacgs-dev \
  --name postgres-connection-string \
  --value "postgresql://ipacgsadmin:${POSTGRES_ADMIN_PASSWORD}@$(az deployment sub show -n <deployment-name> --query properties.outputs.postgresFqdn.value -o tsv)/ipacgs"
```

The API's managed identity has `Key Vault Secrets User` — read-only, no
ability to list or manage other secrets, and no admin keys anywhere in the
container image or its environment variables.

## App registration (Entra ID) — not yet in Bicep

Bicep's support for Entra ID app registrations is still limited enough that
this is done via CLI rather than declaratively. `scripts/create-app-registrations.sh`
has the commands — review and run manually once you're ready to wire up
`FR-IAM-001…004`. It is **not** run automatically by anything in this repo.

## Environments

`dev`, `test` and `prod` are separate resource groups, separate databases,
separate everything — no shared state between them. `prod` additionally gets
zone-redundant HA on Postgres, geo-redundant storage, and purge protection on
Key Vault; `dev`/`test` deliberately don't, to keep them cheap to tear down
and recreate.

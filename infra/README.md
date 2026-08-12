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

   If `az login` fails with **"Your sign-in was successful but you don't
   have permission to access this resource"**, that's Entra ID blocking the
   Azure CLI application itself (a common tenant restriction) — not a
   subscription/RBAC problem, and not something a CLI retry fixes. Two ways
   around it without needing a Global Administrator:
   - **Azure Cloud Shell** (the `>_` icon in portal.azure.com, or
     shell.azure.com) inherits your portal session instead of going through
     the restricted app — often works even when `az login` doesn't. Run the
     rest of this walkthrough from there instead.
   - Otherwise, someone with Cloud Application Administrator rights needs to
     check **Entra admin center → Enterprise Applications → "Azure CLI" →
     Properties → "Assignment required?"** and either add your account or
     turn that off.

2. **Get your own object ID** and put it in `main.dev.bicepparam` in place
   of the placeholder GUID — `platformAdminPrincipalType` already defaults
   to `User`, so this works without any Groups Administrator role:
   ```bash
   az ad signed-in-user show --query id -o tsv
   ```
   A real "IPACGS Platform Admins" group is worth creating once someone has
   the rights to (`az ad group create`), and prod's `.bicepparam` already
   expects one (`platformAdminPrincipalType = 'Group'`) — but nothing about
   dev/test depends on that existing first.

3. **Generate a Postgres admin password** and keep it somewhere real (a
   password manager, not a note) — you'll need it again for the connection
   string in step 5. Export it as an environment variable; the `.bicepparam`
   files read it via `readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD')`
   rather than taking it as a separate CLI override — `.bicepparam` files
   are validated as a complete, self-contained set of parameters, so
   `--parameters main.dev.bicepparam --parameters postgresAdminPassword=...`
   does **not** merge the way a classic JSON parameters file would (fails
   with `BCP258`):
   ```bash
   export POSTGRES_ADMIN_PASSWORD=$(openssl rand -base64 24)
   ```
   If you start a new shell session (including a fresh Cloud Shell session
   after it recycles), re-export this before deploying again — it doesn't
   persist on its own.

4. **Validate before deploying:**
   ```bash
   az deployment sub what-if \
     --location southafricanorth \
     --template-file main.bicep \
     --parameters main.dev.bicepparam
   ```

5. **Deploy:**
   ```bash
   az deployment sub create \
     --location southafricanorth \
     --template-file main.bicep \
     --parameters main.dev.bicepparam
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

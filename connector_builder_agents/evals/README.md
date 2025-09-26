# Connector Builder Evals

This directory contains evaluation (eval) context for Connector Builder Agents.

Manual Runbook:

```bash
poe build-connector --api-name=Hubspot --existing-connector-name=source-hubspot --existing-config-name=config
poe build-connector --api-name=Jira --existing-connector-name=source-jira --existing-config-name=config
poe build-connector --api-name=Stripe --existing-connector-name=source-stripe --existing-config-name=config
```

Not yet tested to succeed:

```bash
# Sentry seems to maybe be working, but runs into timeout issues
# perhaps due to data volumes.
poe build-connector --api-name=Sentry --existing-connector-name=source-sentry --existing-config-name=config

# Complaints of the auth not having the necessary access.
# Could be an auth issue or just not using the OAuth/endpoints correctly.
poe build-connector --api-name="Sharepoint Lists" --existing-connector-name=source-microsoft-lists --existing-config-name=config --additional-instructions="Start with the 'lists' API endpoint to get a list of lists."

# Auth is notoriously a bit weird for Google. The integ auth is in JSON form (in an env var),
# but the API might want it more granular or as a file.
poe build-connector --api-name="Google Analytics v4" --existing-connector-name=source-google-analytics-v4 --existing-config-name=service_config
```

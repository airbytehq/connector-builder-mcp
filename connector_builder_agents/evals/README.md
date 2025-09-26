# Connector Builder Evals

This directory contains evaluation (eval) context for Connector Builder Agents.

Manual Runbook:

```bash
poe build-connector --api-name=Hubspot --existing-connector-name=source-hubspot --existing-config-name=config
poe build-connector --api-name="Sharepoint Lists" --existing-connector=source-microsoft-lists --existing-config-name=config
poe build-connector --api-name=Jira --existing-connector-name=source-jira --existing-config-name=config
poe build-connector --api-name=Sentry --existing-connector-name=source-sentry --existing-config-name=config
poe build-connector --api-name=Stripe --existing-connector-name=source-stripe --existing-config-name=config
poe build-connector --api-name="Google Analytics v4" --existing-connector-name=source-google-analytics-v4 --existing-config-name=service_config
```

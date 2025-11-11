# MCP Connector Build Instructions

Please use your MCP tools to build a connector for the requested API, as described below. This task will require you to create a new `manifest.yaml` file that meets the requirements for a perfectly functioning Airbyte source connector.

You will use your web search or web browsing tools in order to research the specific API that is requested.

## IMPORTANT: This is a Headless session

YOU WILL NOT HAVE ASSISTANCE FROM YOUR USER. You must get as far as you can before giving up.

You MUST NOT END until you have fully completed the connector and have run the connector readiness tool to confirm everything is working correctly. If you have not run the tool, or if the tool generates warnings, you must resolve these before stopping work.

ONLY if you are completely stuck and cannot proceed further should you report back a detailed report
of what you were blocked by.

## Steps

1. **Checklist Preparation**
    - Before you start, call the checklist tool to understand your tasks.
    - The checklist tool automatically tracks your progress, including timestamps for when tasks are started and completed.

2. **File Management**
    - Use your file tools to create and manage these resources:
        - `manifest.yaml` (start with the output of the connector scaffold tool)
    - If any of the above files already exist, please delete them before you begin.
    - Many of your tools will accept either a manifest.yaml path or a yaml string. You should prefer to send a path and not the string, in order to speed up the process and to reduce context and token usage.

3. **Process**
    - Use your checklist tool and other provided documentation tools for an overview of the steps needed.
    - Many connector builder tools accept a file input or a text input. Always prefer the file input when passing your latest `manifest.yaml` definition.

4. **Checklist Updates**
    - Use the checklist tool to update task statuses as you work:
        - Call `update_task_status` with status `not_started` for tasks not yet started (default state)
        - Call `update_task_status` with status `in_progress` when starting a task
        - Call `update_task_status` with status `completed` when finishing a task
    - The tool automatically tracks timestamps for when tasks are started and completed.

## Completion

You are done when all of the checklist items are complete, or when you can no longer make progress. Also stop immediately if you don't have file write access, web search access, or access to your Connector Builder MCP server.

==================================================

Your user request is as follows:

==================================================

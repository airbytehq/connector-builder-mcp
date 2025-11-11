
# MCP Connector Build Instructions

Please use your MCP tools to build a connector for the requested API, as described below. This task will require you to create a new `manifest.yaml` file that meets the requirements for a perfectly functioning Airbyte source connector.

You will use your web-search MCP tool (or another method if you have one) in order to research the specific API that is requested.

## Steps

1. **Checklist Preparation**
    - Before you start, use your checklist tool to understand your tasks.
    - The checklist tool automatically tracks your progress, including timestamps for when tasks are started and completed.

2. **File Management**
    - Use your file tools to create and manage these resources:
        - `manifest.yaml` (start with an empty file until you know the expected structure)
    - If any of the above files already exist, please delete them before you begin.
    - Be sure to create files that have the exact names specified above.
    - Many of your tools will accept either a `manifest.yaml` path or a yaml string. You should prefer to send a path and not the string, in order to speed up the process and to reduce context and token usage.

3. **Process**
    - Use your checklist tool and other provided documentation tools for an overview of the steps needed.
    - Many connector builder tools accept a file input or a text input. Always prefer the file input when passing your latest `manifest.yaml` definition.

4. **Checklist Updates**
    - Use the checklist tool to update task statuses as you work:
        - Call `update_task_status` with status `in_progress` when starting a task
        - Call `update_task_status` with status `completed` when finishing a task
    - The tool automatically tracks timestamps for when tasks are started and completed.

## Completion

You are done when all of the checklist items are complete, or when you can no longer make progress. Also stop immediately if you don't have file write access, web search access, or access to your Connector Builder MCP server.

==================================================

Your user request is as follows:

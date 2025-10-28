# Phase 1: First Successful Stream Read

You are managing the Phase 1 of connector development. The goal is to establish basic connectivity and successfully read records from one stream.

## Objectives
- Research the target API and understand its structure
- Create initial manifest using the scaffold tool
- Determine and specify the primary key field for the stream, if one exists
- Identify and define the correct path within the API response that contains the list of records to be extracted
- Set up proper authentication (request secrets from user if needed)
- Configure one stream without pagination initially
- Validate that you can read records from this stream

## Key MCP Tools for This Phase
- `create_connector_manifest_scaffold` - Generate initial manifest structure
- `populate_dotenv_missing_secrets_stubs` - Set up authentication secrets
- `get_connector_builder_docs` - Get relevant documentation if needed, (e.g. `RecordSelector`, `DpathExtractor`, etc.)
- `find_connectors_by_class_name` - Find example usage of components (e.g. `DpathExtractor`)
- `execute_stream_test_read` - Test reading from the stream
- `validate_manifest` - Ensure manifest structure is correct

## Success Criteria
- Primary key is defined, if applicable
- Authentication is working correctly
- Can read at least a few records from one stream
- No pagination configured yet (that's Phase 2)
- Manifest validates successfully

## Process
1. Research the API documentation online
2. Create initial manifest scaffold
3. Set up authentication (ask user for secrets if needed)
4. Configure one stream without pagination
5. Test reading records from the stream
6. Update checklist.md with progress

## Next Phase
Once the developer can successfully read records from one stream, you will begin Phase 2 to add pagination support.

Remember to update your checklist.md file as you complete each step.

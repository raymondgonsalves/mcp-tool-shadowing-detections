// =============================================================================
//  dcr.bicep — Data Collection Rule for the MCP Tool Shadowing Detection Pack
// =============================================================================
//
//  PURPOSE
//  -------
//  Declarative, version-controlled definition of the Data Collection Rule that
//  ingests parsed MCP protocol events into the MCPProtocolLogs_CL custom table
//  in Microsoft Sentinel (Log Analytics workspace law-mcp-detection-lab).
//
//  WHY THIS FILE EXISTS (the fix this template encodes)
//  ----------------------------------------------------
//  The DCR was originally created by the Sentinel custom-table portal wizard.
//  The wizard generated a pass-through transform: transformKql = 'source'.
//
//  Symptom observed: every ingested row's TimeGenerated column held the
//  ingestion timestamp (~4s after upload) instead of the real MCP event
//  timestamp the forwarder sends in its JSON payload (e.g. the April 30
//  capture times). Confirmed by evidence: the forwarder's pre-upload payload
//  contained the correct ISO-8601 event time, but every row in the table
//  showed a constant 4-second delta between TimeGenerated and ingestion_time()
//  — the fingerprint of the ingestion pipeline generating TimeGenerated
//  itself rather than binding the inbound value.
//
//  Root cause: TimeGenerated is a reserved column in Azure Monitor Logs. With
//  the Logs Ingestion API, an inbound TimeGenerated is only bound into the
//  column if the DCR transform EXPLICITLY projects/extends it. A bare
//  transformKql of 'source' does not — so the pipeline substitutes its own
//  ingestion-stage timestamp upstream of the transform.
//
//  Fix: the transform explicitly re-binds TimeGenerated from the source data:
//      source | extend TimeGenerated = todatetime(TimeGenerated)
//
//  This preserves each source's intended timestamp:
//    - Claude Desktop rows  -> real per-event time parsed from mcp.log
//    - ollmcp rows          -> the now()-stamped fallback the forwarder sets
//                              (ollmcp's terminal capture has no per-event
//                              timestamps; ingestion-time fallback is the
//                              honest value and is preserved as-is)
//
//  DEPLOYMENT NOTE
//  ---------------
//  Deploying this template with the SAME name (dcr-mcp-detection-lab) performs
//  an in-place update. The DCR's immutableId is preserved across the update,
//  so the forwarder's CONFIG (which references the immutable ID and DCE URL)
//  requires no changes. Read-only properties present in the raw `az ... show`
//  export (id, etag, provisioningState, systemData, immutableId) are
//  deliberately omitted — including them causes deployment rejection.
// =============================================================================

@description('Azure region for the DCR. Must match the workspace/DCE region.')
param location string = 'eastus'

@description('Name of the Data Collection Rule. Keep stable — same name = in-place update, immutable ID preserved.')
param dcrName string = 'dcr-mcp-detection-lab'

@description('Resource ID of the Data Collection Endpoint the DCR is associated with.')
param dataCollectionEndpointId string = '/subscriptions/5faad216-600c-4e82-aded-965522b51146/resourceGroups/rg-sentinel-mcp-detection-lab/providers/Microsoft.Insights/dataCollectionEndpoints/dce-mcp-detection-lab'

@description('Resource ID of the destination Log Analytics workspace.')
param workspaceResourceId string = '/subscriptions/5faad216-600c-4e82-aded-965522b51146/resourceGroups/rg-sentinel-mcp-detection-lab/providers/Microsoft.OperationalInsights/workspaces/law-mcp-detection-lab'

// Logical name for the Log Analytics destination, referenced by the dataFlow.
// Value is arbitrary but must be consistent between destinations and dataFlows.
var logAnalyticsDestinationName = 'd0f3187bec3542819cb652a34418236a'

resource dcr 'Microsoft.Insights/dataCollectionRules@2023-03-11' = {
  name: dcrName
  location: location
  properties: {
    dataCollectionEndpointId: dataCollectionEndpointId

    // ---- Inbound stream shape: the 23-column MCPProtocolLogs_CL schema ----
    // Mirrors Schema v1.1 exactly. TimeGenerated is declared datetime so the
    // explicit transform bind below lands a typed value, not a string.
    streamDeclarations: {
      'Custom-MCPProtocolLogs_CL': {
        columns: [
          { name: 'TimeGenerated', type: 'datetime' }
          { name: 'EventType', type: 'string' }
          { name: 'SessionId', type: 'string' }
          { name: 'HostApp', type: 'string' }
          { name: 'ModelName', type: 'string' }
          { name: 'ServerName', type: 'string' }
          { name: 'ServerVersion', type: 'string' }
          { name: 'ServerTransport', type: 'string' }
          { name: 'ToolName', type: 'string' }
          { name: 'ToolDescription', type: 'string' }
          { name: 'ToolDescriptionHash', type: 'string' }
          { name: 'ToolDescriptionLength', type: 'int' }
          { name: 'ToolParameters', type: 'dynamic' }
          { name: 'CallId', type: 'string' }
          { name: 'CallParameters', type: 'dynamic' }
          { name: 'UserPromptHash', type: 'string' }
          { name: 'ConfidenceClaim', type: 'string' }
          { name: 'ResultStatus', type: 'string' }
          { name: 'ResultLength', type: 'int' }
          { name: 'ResultContainsInstructions', type: 'boolean' }
          { name: 'IngestionAgent', type: 'string' }
          { name: 'SchemaVersion', type: 'string' }
          { name: 'RawEvent', type: 'string' }
        ]
      }
    }

    destinations: {
      logAnalytics: [
        {
          name: logAnalyticsDestinationName
          workspaceResourceId: workspaceResourceId
        }
      ]
    }

    dataFlows: [
      {
        streams: [
          'Custom-MCPProtocolLogs_CL'
        ]
        destinations: [
          logAnalyticsDestinationName
        ]
        outputStream: 'Custom-MCPProtocolLogs_CL'

        // *** THE FIX ***
        // Was: 'source'  (pass-through; did NOT bind inbound TimeGenerated,
        //                  so the pipeline substituted ingestion time).
        // Now: explicit extend forces the inbound TimeGenerated value to be
        //      bound into the reserved column. todatetime() makes the typed
        //      conversion explicit and is a no-op if already datetime.
        transformKql: 'source | extend TimeGenerated = todatetime(TimeGenerated)'
      }
    ]
  }
}

@description('Immutable ID of the DCR — unchanged by in-place update; the forwarder CONFIG references this.')
output dcrImmutableId string = dcr.properties.immutableId

@description('Resource ID of the deployed DCR.')
output dcrResourceId string = dcr.id

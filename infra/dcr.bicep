// =============================================================================
//  dcr.bicep — Data Collection Rule for the MCP Tool Shadowing Detection Pack
//  REVISION 2 — coordinated TimeGenerated reserved-column fix
// =============================================================================
//
//  WHY REVISION 2 EXISTS
//  ---------------------
//  Revision 1 attempted: transformKql = 'source | extend TimeGenerated =
//  todatetime(TimeGenerated)'. That FAILED (no-op) because TimeGenerated is
//  a reserved column: an inbound JSON field of that name is not bound as
//  data — the ingestion pipeline substitutes its own ingestion-time value
//  BEFORE the transform runs, so the transform copied the already-wrong
//  value onto itself. Confirmed against Microsoft Learn "Send data to Azure
//  Monitor Logs with Logs ingestion API" tutorial.
//
//  THE COORDINATED FIX (this file + forwarder rename, deployed together):
//    - Forwarder now emits the timestamp under the NON-reserved wire field
//      name "EventTime" (was "TimeGenerated").
//    - This DCR declares "EventTime" as the inbound stream column (NOT
//      TimeGenerated).
//    - The transform CREATES the reserved TimeGenerated column from the
//      inbound EventTime, then drops EventTime:
//        source | extend TimeGenerated = todatetime(EventTime)
//               | project-away EventTime
//
//  WIRE vs STORED SCHEMA (deliberate design — document in schema doc):
//    - Wire schema (what the forwarder POSTs): uses EventTime.
//    - Stored schema (the MCPProtocolLogs_CL table): uses TimeGenerated,
//      created by the transform. The Schema_Document must note this split.
//
//  TIMESTAMP SEMANTICS PRESERVED PER SOURCE:
//    - Claude rows: EventTime = real parsed mcp.log event time -> stored
//      TimeGenerated reflects true event time.
//    - ollmcp rows: EventTime = forwarder now() fallback (ollmcp has no
//      per-event timestamps) -> honest available value for that source.
//      Both behaviours are intentional and preserved.
//
//  DEPLOYMENT: same name (dcr-mcp-detection-lab) = in-place update,
//  immutableId preserved, forwarder CONFIG unchanged. Read-only properties
//  (id/etag/provisioningState/systemData/immutableId) intentionally omitted.
// =============================================================================

@description('Azure region for the DCR. Must match the workspace/DCE region.')
param location string = 'eastus'

@description('Name of the Data Collection Rule. Stable — same name = in-place update, immutable ID preserved.')
param dcrName string = 'dcr-mcp-detection-lab'

@description('Resource ID of the Data Collection Endpoint the DCR is associated with.')
param dataCollectionEndpointId string = '/subscriptions/5faad216-600c-4e82-aded-965522b51146/resourceGroups/rg-sentinel-mcp-detection-lab/providers/Microsoft.Insights/dataCollectionEndpoints/dce-mcp-detection-lab'

@description('Resource ID of the destination Log Analytics workspace.')
param workspaceResourceId string = '/subscriptions/5faad216-600c-4e82-aded-965522b51146/resourceGroups/rg-sentinel-mcp-detection-lab/providers/Microsoft.OperationalInsights/workspaces/law-mcp-detection-lab'

// Logical name for the Log Analytics destination, referenced by the dataFlow.
var logAnalyticsDestinationName = 'd0f3187bec3542819cb652a34418236a'

resource dcr 'Microsoft.Insights/dataCollectionRules@2023-03-11' = {
  name: dcrName
  location: location
  properties: {
    dataCollectionEndpointId: dataCollectionEndpointId

    // ---- INBOUND stream shape ----
    // The wire schema the forwarder POSTs. Column 1 is EventTime (NOT the
    // reserved TimeGenerated). The transform below creates TimeGenerated
    // from EventTime. All other columns unchanged from Schema v1.1.
    streamDeclarations: {
      'Custom-MCPProtocolLogs_CL': {
        columns: [
          { name: 'EventTime', type: 'datetime' }   // was TimeGenerated; wire field
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

        // *** THE FIX (Revision 2) ***
        // Create the reserved TimeGenerated column from the inbound,
        // non-reserved EventTime field, then drop EventTime so it does
        // not appear as a redundant column in the stored table.
        transformKql: 'source | extend TimeGenerated = todatetime(EventTime)'
      }
    ]
  }
}

@description('Immutable ID of the DCR — unchanged by in-place update; the forwarder CONFIG references this.')
output dcrImmutableId string = dcr.properties.immutableId

@description('Resource ID of the deployed DCR.')
output dcrResourceId string = dcr.id

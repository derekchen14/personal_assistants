export interface FlowEntry {
    name: string;
    dax: string;
    description: string;
}

export interface IntentGroup {
    label: string;
    flows: FlowEntry[];
}

export const FLOW_MENU: IntentGroup[] = [
    {
        label: 'Clean',
        flows: [
            { name: 'update', dax: '006', description: 'Modify cell values or column types' },
            { name: 'datatype', dax: '06E', description: 'Validate and cast column types' },
            { name: 'dedupe', dax: '7BD', description: 'Remove duplicate rows' },
            { name: 'fill', dax: '5BD', description: 'Fill null cells' },
            { name: 'replace', dax: '04C', description: 'Find and replace values' },
            { name: 'validate', dax: '16E', description: 'Check rules and normalize formats' },
            { name: 'format', dax: '06B', description: 'Format values into correct form' },
            { name: 'interpolate', dax: '02B', description: 'Estimate missing values from data' },
        ],
    },
    {
        label: 'Transform',
        flows: [
            { name: 'insert', dax: '005', description: 'Add a row or column' },
            { name: 'delete', dax: '007', description: 'Remove rows or columns' },
            { name: 'join', dax: '05A', description: 'Join two tables on a key' },
            { name: 'append', dax: '05B', description: 'Stack rows from another table' },
            { name: 'reshape', dax: '06A', description: 'Pivot, melt, or transpose' },
            { name: 'merge', dax: '56C', description: 'Combine columns' },
            { name: 'split', dax: '5CD', description: 'Split a column' },
            { name: 'define', dax: '28C', description: 'Create a reusable formula' },
        ],
    },
    {
        label: 'Analyze',
        flows: [
            { name: 'query', dax: '001', description: 'Run a SQL query' },
            { name: 'lookup', dax: '002', description: 'Find a metric definition' },
            { name: 'pivot', dax: '01A', description: 'Cross-tabulate' },
            { name: 'describe', dax: '02A', description: 'Describe dataset or column' },
            { name: 'compare', dax: '12A', description: 'Compare two variables' },
            { name: 'segment', dax: '12C', description: 'Drill down a metric by dimension' },
            { name: 'exist', dax: '14C', description: 'Check if data exists' },
        ],
    },
    {
        label: 'Report',
        flows: [
            { name: 'plot', dax: '003', description: 'Create a chart' },
            { name: 'trend', dax: '023', description: 'Compare across time' },
            { name: 'dashboard', dax: '03A', description: 'Schedule recurring reports' },
            { name: 'export', dax: '03D', description: 'Export to file' },
            { name: 'summarize', dax: '019', description: 'Summarize a specific chart or table' },
            { name: 'style', dax: '03E', description: 'Format table display' },
            { name: 'design', dax: '038', description: 'Adjust chart visuals' },
        ],
    },
    {
        label: 'Converse',
        flows: [
            { name: 'chat', dax: '000', description: 'Open conversation' },
            { name: 'preference', dax: '048', description: 'Set a preference' },
            { name: 'recommend', dax: '049', description: 'Get suggestions' },
            { name: 'undo', dax: '08F', description: 'Reverse last action' },
            { name: 'approve', dax: '09E', description: 'Confirm suggestion' },
            { name: 'reject', dax: '09F', description: 'Decline suggestion' },
            { name: 'explain', dax: '009', description: 'Ask what the agent did or plans to do' },
        ],
    },
    {
        label: 'Plan',
        flows: [
            { name: 'insight', dax: '146', description: 'Complex multi-step analysis' },
            { name: 'pipeline', dax: '156', description: 'ETL pipeline' },
            { name: 'blank', dax: '46B', description: 'Find missing values' },
            { name: 'issue', dax: '16F', description: 'Detect data quality issues' },
            { name: 'outline', dax: '16D', description: 'Multi-step plan from instructions' },
        ],
    },
];

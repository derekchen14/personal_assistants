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
        label: 'Explore',
        flows: [
            { name: 'status', dax: '01A', description: 'View current state of the config being built' },
            { name: 'lessons', dax: '01B', description: 'Browse stored lessons and patterns' },
            { name: 'browse', dax: '001', description: 'Look up a specific spec file or section' },
            { name: 'recommend', dax: '18C', description: "Find specs relevant to the user's target domain" },
            { name: 'summarize', dax: '19A', description: 'Agent summarizes overall build progress' },
            { name: 'explain', dax: '19C', description: 'Agent explains an architecture concept' },
            { name: 'inspect', dax: '1AD', description: 'Inspect a draft config section in detail' },
            { name: 'compare', dax: '1CD', description: 'Compare draft config section against spec requirements' },
        ],
    },
    {
        label: 'Provide',
        flows: [
            { name: 'scope', dax: '02A', description: 'Define assistant scope \u2014 name, task, boundaries' },
            { name: 'teach', dax: '02B', description: 'Share a learning or pattern for Kalli to remember' },
            { name: 'intent', dax: '05A', description: 'Provide a domain intent definition' },
            { name: 'revise', dax: '06A', description: 'Update a previously defined config section' },
            { name: 'remove', dax: '07A', description: 'Remove a config section or entry' },
            { name: 'persona', dax: '28A', description: 'Define persona preferences \u2014 tone, name, style, colors' },
            { name: 'entity', dax: '2AC', description: 'Define key entities grounded in domain concepts' },
        ],
    },
    {
        label: 'Design',
        flows: [
            { name: 'propose', dax: '03A', description: 'Review proposed core dacts for the domain' },
            { name: 'rework', dax: '03D', description: 'Revise an in-progress flow design' },
            { name: 'approve', dax: '0AE', description: 'Approve a proposed flow or dact' },
            { name: 'decline', dax: '0AF', description: 'Reject a proposed flow or dact with reason' },
            { name: 'suggest', dax: '39A', description: 'Agent suggests new flows; user reviews' },
            { name: 'refine', dax: '3AD', description: "Refine a flow's slot signature or output type" },
            { name: 'validate', dax: '3AC', description: 'Validate current flow catalog against spec rules' },
        ],
    },
    {
        label: 'Deliver',
        flows: [
            { name: 'generate', dax: '004', description: 'Generate domain config files' },
            { name: 'package', dax: '48A', description: 'Package the full domain for deployment' },
            { name: 'test', dax: '4BC', description: 'Run validation tests against the assistant' },
            { name: 'deploy', dax: '4AE', description: 'Deploy to staging or production' },
            { name: 'secure', dax: '89A', description: 'Configure auth, API keys, and permissions' },
            { name: 'version', dax: '4AD', description: 'Tag a release version with changelog' },
        ],
    },
];

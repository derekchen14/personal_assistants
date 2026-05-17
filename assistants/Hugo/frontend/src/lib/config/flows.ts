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
        label: 'Research',
        flows: [
            { name: 'browse', dax: '012', description: 'Browse tagged content and saved notes for ideas' },
            { name: 'summarize', dax: '19A', description: 'Summarize a post into a short paragraph' },
            { name: 'check', dax: '0AD', description: 'Check post metadata and publication status' },
            { name: 'inspect', dax: '1AD', description: 'Analyze word count, reading time, and content metrics' },
            { name: 'find', dax: '001', description: 'Search previous posts by keyword or topic' },
            { name: 'compare', dax: '18A', description: 'Compare style or structure across posts' },
            { name: 'diff', dax: '0BD', description: 'Compare two versions of a section side by side' },
        ],
    },
    {
        label: 'Draft',
        flows: [
            { name: 'brainstorm', dax: '39D', description: 'Brainstorm new ideas or angles for a topic' },
            { name: 'create', dax: '05A', description: 'Start a new post from scratch' },
            { name: 'outline', dax: '002', description: 'Generate outline options for a topic' },
            { name: 'refine', dax: '02B', description: 'Refine a specific section of the outline' },
            { name: 'cite', dax: '15B', description: 'Add a citation to a sentence or phrase' },
            { name: 'compose', dax: '003', description: 'Write a section from scratch' },
            { name: 'add', dax: '005', description: 'Add sub-sections or an image to an existing section' },
        ],
    },
    {
        label: 'Revise',
        flows: [
            { name: 'rework', dax: '006', description: 'Major revision of draft content based on feedback' },
            { name: 'polish', dax: '3BD', description: 'Polish and refine a specific section' },
            { name: 'tone', dax: '38A', description: 'Adjust tone or style across the post' },
            { name: 'audit', dax: '13A', description: "Check consistency with the user's previous posts" },
            { name: 'simplify', dax: '7BD', description: 'Reduce complexity of a section or note' },
            { name: 'remove', dax: '007', description: 'Remove a section or delete a draft' },
            { name: 'tidy', dax: '3AB', description: 'Normalize heading levels and whitespace' },
        ],
    },
    {
        label: 'Publish',
        flows: [
            { name: 'release', dax: '04A', description: 'Publish the post to the primary blog' },
            { name: 'syndicate', dax: '04C', description: 'Cross-post to a specific platform' },
            { name: 'schedule', dax: '4AC', description: 'Schedule a post for future publication' },
            { name: 'preview', dax: '4AD', description: 'Preview how the post will look when published' },
            { name: 'promote', dax: '004', description: 'Pin, feature, or announce a post' },
            { name: 'cancel', dax: '04F', description: 'Cancel or unpublish a post' },
            { name: 'survey', dax: '01C', description: 'View configured publishing channels' },
        ],
    },
];

export const FLOW_TO_DAX: Record<string, string> = Object.fromEntries(
    FLOW_MENU.flatMap(g => g.flows.map(f => [f.name, f.dax]))
);

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
            { name: 'browse', dax: '012', description: 'Browse available topic ideas' },
            { name: 'find', dax: '001', description: 'Search previous posts by keyword or topic' },
            { name: 'view', dax: '1AD', description: 'View a specific post or draft in detail' },
            { name: 'check', dax: '0AD', description: 'Check current draft posts and their status' },
            { name: 'inspect', dax: '1BD', description: 'Analyze word count, reading time, and content metrics' },
            { name: 'compare', dax: '18A', description: 'Compare style or structure across posts' },
            { name: 'diff', dax: '0BD', description: 'Compare two versions of a section side by side' },
            { name: 'survey', dax: '01C', description: 'View configured publishing channels' },
        ],
    },
    {
        label: 'Draft',
        flows: [
            { name: 'outline', dax: '002', description: 'Generate outline options for a topic' },
            { name: 'compose', dax: '003', description: 'Write a section from scratch' },
            { name: 'refine', dax: '02B', description: 'Refine a specific section of the outline' },
            { name: 'expand', dax: '03A', description: 'Expand bullet points or notes into full prose' },
            { name: 'add', dax: '005', description: 'Add a new section to the post' },
            { name: 'create', dax: '05A', description: 'Start a new post from scratch' },
            { name: 'brainstorm', dax: '29A', description: 'Hugo brainstorms ideas for a topic' },
        ],
    },
    {
        label: 'Revise',
        flows: [
            { name: 'rework', dax: '006', description: 'Major revision of draft content based on feedback' },
            { name: 'polish', dax: '3BD', description: 'Polish and refine a specific section' },
            { name: 'tone', dax: '38A', description: 'Adjust tone or style across the post' },
            { name: 'audit', dax: '13A', description: "Check consistency with the user's previous posts" },
            { name: 'format', dax: '3AD', description: 'Format the post for publication' },
            { name: 'tidy', dax: '3AB', description: 'Normalize heading levels and whitespace' },
            { name: 'remove', dax: '007', description: 'Remove a section or delete a draft' },
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
        ],
    },
];

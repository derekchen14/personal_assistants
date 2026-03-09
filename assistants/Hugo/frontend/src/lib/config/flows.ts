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
            { name: 'search', dax: '01A', description: 'Search previous blog posts by keyword' },
            { name: 'view', dax: '1AD', description: 'View a specific post or draft in detail' },
            { name: 'survey', dax: '01C', description: 'View configured publishing platforms' },
            { name: 'check', dax: '0AD', description: 'Check current draft posts and their status' },
            { name: 'explain', dax: '19A', description: 'Hugo explains a writing or blogging concept' },
            { name: 'find', dax: '1AB', description: 'Find related content across existing posts' },
            { name: 'compare', dax: '18A', description: 'Compare style or structure across posts' },
            { name: 'diff', dax: '0BD', description: 'Compare two versions of a section side by side' },
        ],
    },
    {
        label: 'Draft',
        flows: [
            { name: 'outline', dax: '02A', description: 'Generate outline options for a topic' },
            { name: 'select', dax: '2AE', description: 'Select and approve an outline to work with' },
            { name: 'refine', dax: '02B', description: 'Refine a specific section of the outline' },
            { name: 'expand', dax: '03A', description: 'Expand outline into full prose' },
            { name: 'write', dax: '03B', description: 'Write or rewrite a specific section' },
            { name: 'add', dax: '05B', description: 'Add a new section to the post' },
            { name: 'create', dax: '05A', description: 'Start a new post from scratch' },
            { name: 'brainstorm', dax: '29A', description: 'Hugo brainstorms ideas for a topic' },
        ],
    },
    {
        label: 'Revise',
        flows: [
            { name: 'rework', dax: '03D', description: 'Major revision of draft content based on feedback' },
            { name: 'polish', dax: '3BD', description: 'Polish and refine a specific section' },
            { name: 'tone', dax: '38A', description: 'Adjust tone or style across the post' },
            { name: 'audit', dax: '13A', description: "Check consistency with the user's previous posts" },
            { name: 'format', dax: '3AD', description: 'Format the post for publication' },
            { name: 'accept', dax: '0AE', description: 'Accept and finalize a revision' },
            { name: 'amend', dax: '0AF', description: 'Request further changes to a revision' },
        ],
    },
    {
        label: 'Publish',
        flows: [
            { name: 'release', dax: '04A', description: 'Publish the post to the primary blog' },
            { name: 'syndicate', dax: '04C', description: 'Cross-post to a specific platform' },
            { name: 'schedule', dax: '4AC', description: 'Schedule a post for future publication' },
            { name: 'preview', dax: '4AD', description: 'Preview how the post will look when published' },
            { name: 'promote', dax: '4AE', description: 'Pin, feature, or announce a post' },
            { name: 'cancel', dax: '04F', description: 'Cancel or unpublish a post' },
        ],
    },
];

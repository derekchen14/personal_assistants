import { marked } from 'marked';

marked.setOptions({ breaks: true, gfm: true });

export function md(text: string): string {
    return marked.parse(text) as string;
}

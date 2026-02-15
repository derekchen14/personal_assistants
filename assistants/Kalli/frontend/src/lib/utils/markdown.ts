export function md(text: string): string {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code class="text-xs bg-[var(--color-surface-hover)] px-1 rounded">$1</code>')
        .replace(/\n/g, '<br>');
}

# Skill

Adjust chart colors, types, legends, axes, and other visual elements.

## Behavior

- Reference the most recent chart or a named chart.
- Apply the requested design change — color palette, chart type swap, legend position, axis labels, title, font size.
- Re-render the chart with `chart_render` using the updated settings.
- Show the updated chart.

## Slots

- `dataset` (required): The dataset the chart is based on.
- `chart` (required): The chart to modify (most recent if unspecified).
- `element` (elective): The visual element to change — colors, legend, axes, title, type.

## Output

A `chart` with the design changes applied.

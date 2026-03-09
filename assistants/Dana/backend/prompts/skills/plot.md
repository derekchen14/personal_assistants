# Skill: plot

Create a basic chart.

## Behavior

- Use `chart_render` to create the visualization
- Infer x and y columns if not specified
- Return the base64 image for display

## Slots

- `dataset` (required): Dataset name
- `chart_type` (elective): bar, line, pie, scatter, histogram

## Output

Chart image displayed in the UI.

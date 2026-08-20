# Configurable layouts

Layouts are versioned JSON documents rendered from top to bottom. Later widgets
appear above earlier widgets, which allows panels, images, labels, values, and
bars to be layered deliberately.

The installed service watches the selected layout file. A valid saved change is
used on the next dashboard frame without restarting the service. If a change is
invalid or temporarily incomplete while being saved, the service logs the
problem and keeps displaying the last valid layout.

## Document structure

```json
{
  "version": 1,
  "name": "My dashboard",
  "width": 480,
  "height": 320,
  "background": "#080d18",
  "widgets": []
}
```

Every widget has `kind`, `x`, `y`, `width`, and `height`. Geometry must remain
inside the layout canvas. Unknown fields are rejected so typing mistakes do not
silently produce surprising output.

## Widget types

- `panel`: colored or outlined rounded rectangle used as a background card,
  separator, or decorative shape.
- `label`: fixed text.
- `clock`: current time using a `strftime` format such as `%H:%M:%S`.
- `value`: a formatted live metric.
- `progress`: a live metric represented as a filled bar.
- `image`: PNG, JPEG, or another Pillow-supported image, placed using
  `contain`, `cover`, or `stretch` fitting.

Text widgets support font size, bold styling, color, and left/center/right
alignment. Metric widgets display their `missing` text (default `--`) when a
sensor is unavailable.

## Metric sources

- `cpu_percent`
- `cpu_temp_c`
- `memory_percent`
- `memory_used_gib`
- `memory_total_gib`
- `gpu_name`
- `gpu_percent`
- `gpu_temp_c`
- `gpu_memory_used_gib`
- `gpu_memory_total_gib`

Value formatting accepts either a standard Python format specification or a
small `{value}` template. For example:

```json
{
  "kind": "value",
  "x": 30,
  "y": 95,
  "width": 150,
  "height": 44,
  "source": "cpu_percent",
  "format": "{value:.0f}%",
  "font_size": 31,
  "bold": true
}
```

## Safety boundaries

The format contains data and styling only. It cannot execute commands, Python,
or shell code. Image paths are resolved relative to the layout file unless they
are absolute. Invalid geometry, unsupported versions, unknown widget or metric
names, and invalid ranges are rejected before rendering.

The JSON format is the stable model beneath the planned visual editor. Users
do not need to edit JSON directly. Run `hongtai-editor` to edit the layout
selected in the saved application configuration, or use
`hongtai-editor --layout PATH` to work on a separate profile. The editor binds
to localhost only, validates every save using the same layout model as the
panel service, and atomically replaces the file only after validation succeeds.

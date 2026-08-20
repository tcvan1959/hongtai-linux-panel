# Hongtai Linux Panel

Linux support for Hongtai-based USB system-monitor displays.

The physically accepted v1 path provides explicit, foreground-only Linux
control of one verified panel: detection, test and dashboard display,
brightness, fail-stop shutdown, and a manual restart that restores the factory
animation. Broader device-family support and unattended operation are not
claimed. Version `0.1.0` is development metadata, not a formal release or tag.

## First verified device

| Property | Verified value |
| --- | --- |
| USB vendor/product | `33c3:7802` |
| USB product | `HONGTAI MONITOR` |
| Model | `TXW818-ST7796-3.5inch-hor` |
| Resolution | 480×320 |
| Firmware | 3.2 |
| Transport | USB CDC ACM at 2,000,000 baud |
| Linux device | `/dev/ttyACM0` |

Linux normally provides a stable path similar to:

```text
/dev/serial/by-id/usb-HONGTAI_MONITOR_SERIAL_PLACEHOLDER-if00
```

Replace `SERIAL_PLACEHOLDER` with the value detected on your system. Use the
stable path when possible; `/dev/ttyACM0` can change when other serial devices
are connected.

## Current capabilities

- Build and validate Hongtai command frames
- Query and parse device information
- Prepare and transmit a static JPEG frame
- Maintain a displayed frame with protocol keepalives
- Render configurable live sensor dashboards
- Test protocol behavior without connected hardware

No command runs automatically. The tools communicate with hardware only when
you invoke them and supply a device path.

## Bounded Linux Direct Driver v1

For the small, fail-stop implementation of the experimentally verified direct
path, run:

```bash
hongtai-direct
```

From an uninstalled checkout at the repository root:

```bash
PYTHONPATH=src python3 -m hongtai_panel.cli_direct
```

It prefers the stable by-id link, verifies USB identity where Linux exposes it,
queries firmware information, requires the device-reported 480×320 geometry,
and streams a time-changing orientation test dashboard at a modest rate. Stop
it with `Ctrl+C`, or use `--duration 10` for a bounded physical check. See
[docs/LINUX-DIRECT-V1.md](docs/LINUX-DIRECT-V1.md) for permissions, exact test
steps, limitations, and the automated-versus-hardware test boundary.

Physical acceptance passed on the test host on August 18, 2026: the bounded
10-second run rendered with correct orientation and shut down cleanly, and a
separate `Ctrl+C` run closed the serial connection cleanly.

## Panel Control App v1

Launch the foreground-only local control app after installation:

```bash
hongtai-control
```

Or run it directly from an uninstalled checkout:

```bash
PYTHONPATH=src python3 -m hongtai_panel.cli_control
```

The app detects and identifies the verified panel, previews the built-in
orientation test and starter dashboard, starts and stops display streaming,
applies validated brightness changes, and can preview and explicitly display a
selected PNG or JPEG still image. In a source checkout, personal images may be
kept outside the repository and selected directly with **Browse / Choose
image**, without copying them into the project. The optional
`display_media/local/` folder remains available for generic checkout-local
media; its contents are ignored by Git and excluded from package artifacts.
Selection and preview never start the panel stream; **Display image** remains a
separate action.

Panel Control also offers an explicit **Restore default display (restarts
panel)** action after streaming is fully stopped. That action sends one verified
board-restart command and leaves re-detection to the user; it does not reconnect
or retry automatically. Use **Exit app** or `Ctrl+C` in the launcher terminal
to stop streaming and close the serial connection. Nothing is installed as a
background service. See
[docs/PANEL-CONTROL-V1.md](docs/PANEL-CONTROL-V1.md) for the runbook, physical
acceptance steps, persistence boundary, and current limitations.

Panel Control App v1 completed physical acceptance on the test host on August
20, 2026. Live display, Stop/blank behavior, the confirmed one-shot restore
action, USB re-enumeration, factory-animation restoration, and subsequent
manual device detection all behaved as designed on the verified firmware 3.2
panel. Display Media Library v1 also completed bounded physical acceptance on
August 20, 2026: external-file selection and preview did not start streaming,
and the explicitly displayed PNG rendered correctly and remained stable.

### Confirmed firmware/USB stall

Firmware 3.2 can enter a state where the tty remains present but writes time
out. In a reproduced occurrence, one controlled USB unbind/rebind did not
recover the panel: it remained visible in `lsusb`, `/dev/ttyACM0` was not
recreated, and Linux reported `can't set config #1, error -110`. The tools must
fail closed after the first communication error; do not add or use aggressive
retry, reset, or unbind/rebind loops. A full host/panel power-cycle
has restored the stalled panel and remains the qualified recovery boundary.
The verified `0x01` action restores the default display on a healthy,
responsive panel; it is not qualified as recovery for this stalled state.

### Known limitations

- Only the device, model, firmware, and resolution listed above are physically
  supported; other Hongtai-family devices remain unverified.
- One visually observed 30-minute low-rate run passed, but repeated,
  unattended, and general long-duration reliability are not proven.
- Stop and Exit end live streaming safely, but the panel becomes blank unless
  the user separately chooses the verified restart action.
- `0x01` is verified on a healthy responsive panel, not on an already wedged
  CDC channel.
- A firmware/USB stall remains possible. Automatic recovery, reconnect loops,
  USB resets, and automatic restart are deliberately not provided by accepted
  v1.

## Development setup

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
```

To install only the library and static-image support:

```bash
python -m pip install -e '.[images]'
```

## Query a panel

```bash
hongtai-query \
  --device /dev/serial/by-id/usb-HONGTAI_MONITOR_SERIAL_PLACEHOLDER-if00
```

The query resets the communication parser, sends the read-only device-info
command (`0x06`), validates the response frame, and prints its JSON payload.

## Display a static image

```bash
hongtai-image picture.png \
  --device /dev/serial/by-id/usb-HONGTAI_MONITOR_SERIAL_PLACEHOLDER-if00
```

The image is converted to a cropped 480×320 JPEG. The tool leaves the firmware
close command disabled by default because command `0x21` left the verified
firmware on a blank screen. Add `--release` only when that behavior is wanted.
The process keeps sending refresh commands until you press `Ctrl+C`; the
verified firmware clears the frame shortly after refresh commands stop. Use
`--hold SECONDS` only for a deliberately time-limited test.

For a repeatable physical-panel check, display the built-in geometry and color
test pattern:

```bash
hongtai-test-pattern \
  --device /dev/serial/by-id/usb-HONGTAI_MONITOR_SERIAL_PLACEHOLDER-if00
```

This command also runs until `Ctrl+C` by default.

## Experimental functionality outside accepted v1

The repository retains earlier foreground-service, standalone-editor, saved
configuration, reconnect, and systemd user-service work for continued research.
These paths are **experimental, unsupported, disabled by default where
applicable, and outside the physically accepted v1 scope**. In particular,
automatic reconnect and automatic startup are not qualified for firmware 3.2
and must not be used for unattended operation.

The experimental foreground service can find one panel and keep selected
content visible:

```bash
hongtai-service
```

With a custom image:

```bash
hongtai-service --image picture.png
```

Or show the starter live dashboard:

```bash
hongtai-service --dashboard
```

The dashboard reads CPU load and memory directly from Linux, CPU temperature
from `k10temp` when available, and GPU telemetry from `nvidia-smi` or the Linux
`amdgpu` interfaces. Missing sensors appear as unavailable rather than stopping
the display.

### Experimental saved configuration

The service reads `~/.config/hongtai-linux-panel/config.json` when it exists.
Use [config/example.json](config/example.json) as the starting format. A
different file can be selected with `--config PATH`, and command-line options
override saved values for one run.

The configuration is versioned and validated before the panel is opened.
Unknown names, unsupported versions, unsafe JPEG quality, invalid geometry, or
an unreasonable update interval stop with a clear configuration error.

The experimental dashboard now defaults to a quality-55 sensor image every 30
seconds. Lightweight refresh commands maintain the visible frame once per
second between those updates. This conservative profile follows physical tests
where full images every second failed after about 16 minutes and every five
seconds failed after about 49 minutes. Dynamic mode is not yet suitable for
automatic startup on firmware 3.2.

`reconnect_enabled` defaults to `false`. This fail-stop behavior is mandatory
for the accepted safety boundary:
firmware 3.2 once became unresponsive after repeated reconnect attempts and
required complete AC power removal. The retained opt-in is experimental and
must not be treated as safe without future device-specific qualification.

Dashboard appearance is also data-driven. The starter dashboard is composed of
independent panel, label, clock, metric, progress, and image widgets. Saved
layout changes reload while the service is running, and invalid changes retain
the last valid display. See [docs/LAYOUTS.md](docs/LAYOUTS.md).

### Experimental standalone layout editor

Launch the editor for the layout selected in the saved configuration:

```bash
hongtai-editor
```

The editor runs only on this computer at `http://127.0.0.1:8765/`. It presents
an exact 480×320 preview where widgets can be selected, dragged, resized,
duplicated, deleted, and configured. Changes remain in the browser until **Save
layout** is pressed. The server validates the complete document and replaces
the layout atomically, so an incomplete or invalid edit cannot overwrite the
working file.

To edit a separate profile or test copy without affecting the selected live
layout:

```bash
hongtai-editor --layout /path/to/layout.json
```

### Experimental automatic login startup

The installer is retained as unaccepted development work. Previewing it does
not alter the system:

```bash
hongtai-install-service
```

The `--install` action changes the user service configuration and enables login
startup. It is **not part of accepted v1 and is not recommended for firmware
3.2**:

```bash
hongtai-install-service --install
```

The installer creates a default dashboard configuration only when none exists,
writes a systemd user service, reloads the user service manager, and enables the
dashboard for login startup. The generated service records both the selected
Python executable and this repository's source directory, so it does not depend
on the shell's working directory or `PYTHONPATH`.

Use `--device PATH` when more than one compatible panel is connected. The
service deliberately refuses to guess between multiple panels. Automatic
startup must remain disabled unless it is separately qualified and explicitly
authorized for the physical firmware.

## Project direction

Possible later development has two layers:

1. An optional background panel service responsible for device discovery,
   carefully qualified recovery, rendering, JPEG encoding, and USB
   communication.
2. A visual editor for choosing sensor widgets or media, arranging a dashboard,
   previewing output, and saving profiles.

See [docs/ROADMAP.md](docs/ROADMAP.md) for staged milestones and
[docs/PROTOCOL.md](docs/PROTOCOL.md) for the verified wire protocol.
The strictly time-limited reply-capture procedure is documented in
[docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md).

## Safety and provenance

Firmware-changing, serial-number, motor, and OTA commands are intentionally
outside the current implementation. The protocol layer is an independent
Python implementation based on documented behavior and physical testing. See
[docs/PROVENANCE.md](docs/PROVENANCE.md).

## License

Copyright 2026 Timothy C. VanDeventer.

Licensed under the Apache License 2.0. See [LICENSE](LICENSE). Implementation
and protocol provenance are recorded in
[docs/PROVENANCE.md](docs/PROVENANCE.md).

# Linux Direct Panel Driver v1

This bounded driver supports one experimentally verified device:

- USB `33c3:7802`, product `HONGTAI MONITOR`
- model `TXW818-ST7796-3.5inch-hor`
- firmware `3.2`
- 480×320, USB CDC ACM, 2,000,000 baud

No support is claimed for other Hongtai or Jungle Leopard devices.

## Requirements and permissions

Use Linux with Python 3.10 or newer and Pillow. Install the project in a
virtual environment with `python -m pip install -e '.[images]'`.

The user running the command must be allowed to open the serial device. On
Ubuntu this commonly means membership in `dialout`; log out and back in after
group membership changes. Do not run the driver as root merely to bypass a
permissions problem.

Discovery first searches Hongtai-named links under `/dev/serial/by-id`. If
none exists, `/dev/ttyACM*` is considered only when Linux sysfs identifies the
endpoint as exactly `33c3:7802`. An explicit path is also rejected when sysfs
proves that it belongs to a different USB device.

## Run and stop

```bash
hongtai-direct
```

From an uninstalled checkout, run the same entry point from the repository
root (after making Pillow available in the active Python environment):

```bash
PYTHONPATH=src python3 -m hongtai_panel.cli_direct
```

An explicit device path can be supplied when necessary:

```bash
hongtai-direct \
  --device /dev/serial/by-id/usb-HONGTAI_MONITOR_SERIAL_PLACEHOLDER-if00
```

The command queries and validates the device before transmitting an image. It
then displays a Linux test dashboard with model identity, time, a color bar,
and distinct `TL`, `TR`, `BL`, and `BR` corner markers. A complete JPEG is sent
every five seconds and lightweight refresh commands are sent every second.

Press `Ctrl+C` once to stop. SIGTERM is handled the same way. The serial file
descriptor is closed deterministically. Command `0x21` is deliberately not
sent during ordinary shutdown because it is known to blank the verified panel.
The panel nevertheless normally blanks shortly after refresh traffic stops;
this is observed firmware live-pipeline timeout behavior.

Brightness is opt-in because it changes visible device state:

```bash
hongtai-direct --brightness 80
```

For a deliberately bounded hardware run:

```bash
hongtai-direct --duration 10
```

The equivalent bounded command from an uninstalled checkout is:

```bash
PYTHONPATH=src python3 -m hongtai_panel.cli_direct --duration 10
```

Failures are printed and return a nonzero exit status; the driver does not
silently reconnect or retry a failing firmware controller.

## Automated versus physical verification

Ordinary automated tests never open a serial device:

```bash
python -m unittest discover -s tests -v
```

They cover frame and checksum construction, response parsing, nested firmware
3.2 JSON, JPEG envelopes, resolution checks, exact/fallback discovery,
brightness payload validation, modest-rate streaming, stop events, and cleanup
state using fakes.

Physical verification is separate and must remain bounded:

1. Confirm `ls -l /dev/serial/by-id/` shows the expected stable link.
2. Run `hongtai-direct --duration 10` as the normal desktop user.
3. Confirm the log reports the expected model, firmware, and 480×320 geometry.
4. Confirm all four labeled corner markers are in the corresponding corners,
   the color bar is correct, text is readable, and the time changes once during
   the run.
5. Confirm the process exits after about ten seconds without an error and the
   serial path remains present.
6. Confirm the panel blanks shortly after the process stops.
7. Repeat with no duration, press `Ctrl+C` once, and confirm the same clean
   shutdown. Do not repeat a failed test in a tight loop.

### Physical acceptance record

Physical acceptance completed successfully on the test host on August 18,
2026:

- The 10-second bounded run rendered correctly with the expected orientation
  and completed its timed shutdown cleanly.
- The separate indefinite run stopped cleanly after one `Ctrl+C` and closed
  the serial connection cleanly.

These results accept the bounded Linux Direct Panel Driver v1 milestone on the
verified `33c3:7802` device. They do not qualify long-duration streaming or any
additional panel model.

## Current limitations

- Only `33c3:7802` at the reported 480×320 geometry is accepted.
- Firmware 3.2 has shown long-duration write stalls during dynamic streaming;
  v1 therefore uses a modest five-second full-frame cadence and fails closed.
- A reproduced stall left the tty present while writes timed out and survived
  one controlled USB unbind/rebind. After rebind the device remained visible
  in `lsusb`, no tty was created, and the kernel reported configuration error
  `-110`. Do not retry, reset, or unbind/rebind in a loop; stop and recover the
  host/panel with a full physical power-cycle before one bounded query.
- A stale USB interface without a `/dev/ttyACM*` node cannot be opened. Recover
  the hardware outside this program before resuming a physical test.
- No daemon, system service, autostart, boot integration, udev rule, Windows
  support, sensor-dashboard integration, or firmware operation is part of this
  bounded driver.

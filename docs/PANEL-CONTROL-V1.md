# Panel Control App v1

Panel Control is a small, foreground-only local app for the accepted Linux
Direct Panel Driver v1. It supports only the physically verified HONGTAI
panel: USB `33c3:7802`, model `TXW818-ST7796-3.5inch-hor`, firmware `3.2`, and
480×320 resolution.

## Launch

Install the project in a virtual environment with image support, then run:

```bash
hongtai-control
```

From an uninstalled checkout, make Pillow available in the active Python
environment and run from the repository root:

```bash
PYTHONPATH=src python3 -m hongtai_panel.cli_control
```

The app starts a loopback-only web interface at `http://127.0.0.1:8765/` and
opens it in the default browser. If the browser should not open automatically,
add `--no-open` and visit the printed local address yourself. Use `--device
PATH` only when an explicit serial path is needed.

## Included controls

- **Detect panel** uses the direct driver's safe by-id/`ttyACM` discovery,
  queries device information, and requires the verified 480×320 geometry.
- Identity fields show device path, model, firmware, and resolution.
- The layout selector previews either the orientation test or the existing
  starter sensor dashboard, plus a selected still image when available.
- **Refresh folder** lists direct-child PNG/JPEG files from the private media
  folder. **Choose library image** prepares the chosen file but does not start
  streaming.
- **Browse / Choose image** accepts a PNG or JPEG elsewhere on the computer,
  prepares it in memory, and does not copy or publish it.
- The current filename and source are visible. **Display image** is enabled
  only after selection and remains the explicit streaming action.
- **Start display** begins modest-rate JPEG streaming and keepalives through
  the accepted direct-driver path.
- The brightness slider accepts `0..100`; **Apply brightness** sends the
  validated one-byte brightness command without interleaving serial writes.
- **Stop display** joins the streaming worker and closes the serial connection.
- **Exit app** first stops streaming, then closes the local app. `Ctrl+C` in
  the launch terminal performs the same foreground cleanup.
- Visible state distinguishes disconnected, detected, starting, streaming,
  stopped, and error conditions. Failed actions show a user-facing message.

## Display Media Library v1

Personal images can remain outside the repository, including in a user's
Pictures directory, and be selected directly with **Browse / Choose image**.
They are decoded and prepared in memory for the current app session and are not
copied into the project. The optional source-checkout library is
`display_media/local/`; it is intended for generic checkout-local media. Its
contents are ignored by Git, pruned from the source distribution, and outside
the Python package tree. The tracked `.gitkeep` only preserves the empty
folder. Installed copies that do not have a checkout use the user's private
data directory (`$XDG_DATA_HOME/hongtai-linux-panel/media`, or the standard
`~/.local/share` equivalent) instead.

Only single-frame PNG and JPEG/JPG files are accepted. The implementation
checks both filename and decoded image format, bounds input size and decoded
pixel count, rejects missing, unreadable, corrupt, GIF, animated, and
unsupported files, then center-crops while preserving aspect ratio and encodes
one 480×320 JPEG through the existing rendering and streaming path. No file
watching, slideshow, animation, video, remote download, or online search is
present.

Selection is app-session state. It is retained after **Stop display**, allowing
the user to display it again or choose another image, but it is not written to
configuration and does not start streaming by itself. Selecting another image
is blocked while streaming; stop the display first. The separate restore action
continues to be the only supported way to return a healthy panel from the
expected blank-after-stop state to its factory animation.

## Persistence and stop behavior

Panel Control does not install, enable, or start a service, daemon, login item,
boot item, or udev rule. It creates no persistent background panel process.
The local listener and streaming worker exist only inside the foreground app
process. After **Stop display**, **Exit app**, or `Ctrl+C`, the worker is joined
and the serial connection is closed.

Firmware 3.2 clears the live image shortly after frames and keepalives stop, so
the physical panel normally becomes blank after Stop or Exit. Command `0x21`
is not sent during normal cleanup.

## Restore-default action

Panel Control v1 exposes a separate, clearly labeled **Restore default display
(restarts panel)** action. A one-shot `0x01` board restart is physically
verified to restore the factory/default animation on the supported firmware,
while ordinary Stop/Exit and `0x21` do not. This must remain an explicit user
action, not part of Stop, Exit, error handling, or startup.

The implemented v1 behavior is:

- enable the action only after the streaming worker has fully stopped and its
  serial connection is closed;
- require a confirmation that explains the temporary USB/tty disconnect and
  re-enumeration, and that the action should not be used on a stalled or
  unresponsive panel;
- open one bounded serial connection, send exactly one `0x01`, close the local
  handle, and enter a distinct restore/restarting state;
- treat the immediate serial disappearance as expected rather than reporting
  the reboot itself as a streaming failure; and
- perform no automatic retry, reopen, query, reset, or unbind/rebind. If the UI
  reports **Waiting for panel restart**, it instructs the user to wait and then
  use **Detect panel** manually. It does not claim visual restoration without
  user confirmation.

The protected restart endpoint also requires an explicit confirmation value;
an unconfirmed request is rejected without invoking the controller. After the
one write, the controller clears the stale tty identity and remains in the
visible restarting state until a manual detection or another explicit user
action changes it.

## Automated and physical verification

The normal suite uses fake panels for controller state, start/stop lifecycle,
brightness validation, layout selection, missing paths, unsupported geometry,
error state, still-image validation, safe fit/crop, private-directory handling,
selection-without-streaming, selected-image display, and selection preservation
after Stop. Loopback HTTP tests cover the control page, media selection/upload,
preview, status, and protected actions. Package inspection verifies that
private media cannot enter the source distribution or wheel through the local
folder. These tests do not open physical serial hardware.

For the Display Media Library v1 physical acceptance, perform exactly one
bounded foreground sequence on a healthy panel:

1. Keep one non-sensitive test PNG/JPEG outside the repository and plan to use
   **Browse / Choose image**. Launch Panel Control and choose **Detect panel**.
2. Select the file. Confirm the current-image label and 480×320 preview are
   correct, and confirm the panel has not started streaming.
3. Choose **Display image** once. Confirm the selected image fills the screen,
   retains its proportions through center cropping, and has the expected
   orientation and colors.
4. After a short stable observation, choose **Stop display** once. Confirm the
   UI reports Stopped and the panel becomes blank as already expected.
5. Choose **Restore default display (restarts panel)** once and accept the
   warning. Confirm the board restarts, USB re-enumerates, and the factory
   animation returns.
6. Stop. Do not repeat automatically. If any communication error occurs, leave
   the app stopped and follow the existing fail-stop boundary.

### Display Media Library v1 physical acceptance record

Display Media Library v1 completed bounded human verification on August 20,
2026. Panel Control launched, detected the verified panel, selected an external
private PNG through **Browse / Choose image**, and showed the correct preview
without automatically starting the stream. The explicit **Display image**
action rendered the image correctly at 480×320, and the physical display
remained stable during the observation. The private test asset stayed outside
the repository and is not named or reproduced in project content.

The previously accepted Stop/blank, one-shot restore, USB re-enumeration, and
manual post-restart detection behavior also completed normally during the
bounded workflow. Animation, video, slideshow, file watching, and remote media
remain outside this milestone.

Use this bounded manual acceptance procedure on the test host:

1. Launch `hongtai-control`, or use the direct-from-source command above.
2. Confirm the Panel Control page opens and initially reports Disconnected.
3. Choose **Detect panel** and confirm the expected path, model, firmware 3.2,
   and 480×320 resolution appear.
4. Select **Orientation test**, confirm its preview, and choose **Start
   display**. Confirm all four physical corner markers and text orientation.
5. Move brightness to a clearly distinguishable safe value, choose **Apply
   brightness**, and confirm the physical backlight changes.
6. Choose **Stop display**. Confirm the UI reports Stopped, the panel blanks
   after its live timeout, and the serial connection is closed.
7. Start once more, then choose **Exit app**. Confirm the display stops, the
   page reports that Panel Control is closed, and the launcher exits.
8. Confirm no `hongtai-control` process remains and no service or automatic
   startup entry was created. Do not repeat a failed hardware action rapidly.

For the restore-default acceptance, perform one additional bounded sequence:

1. Detect the healthy panel, start a live display briefly, then choose **Stop
   display** and verify that the panel is blank.
2. Choose **Restore default display (restarts panel)** and accept the warning.
3. Observe one brief board restart and USB disconnect/re-enumeration; confirm
   the factory/default animation returns.
4. After the stable by-id link returns, manually choose **Detect panel** and
   verify the expected model, firmware 3.2, and 480×320 resolution.
5. Stop. Do not repeat automatically or use this procedure on an already
   stalled or unresponsive panel.

### App-side verification record

On August 18, 2026, the real control app launched on the test host, detected
the stable by-id path, and displayed the expected model, firmware 3.2, and
480×320 geometry. One bounded foreground session reached Streaming, accepted a
brightness change to 60, restored brightness to 80, reached Stopped with the
serial connection closed, and exited with no control process remaining. The
user service was inactive and not enabled/present.

The test environment could inspect the browser UI and serial lifecycle but not
the physical panel surface. Those visual checks were subsequently completed by
the host observer as recorded below; they were not inferred from successful
writes.

### Physical acceptance record

Panel Control App v1 was physically accepted on the test host on August 20,
2026. The healthy verified `33c3:7802`, model
`TXW818-ST7796-3.5inch-hor`, firmware 3.2 panel completed the bounded sequence
as designed:

- live display started and rendered correctly;
- **Stop display** closed the live session and the panel became blank;
- **Restore default display (restarts panel)** sent the explicit restart;
- the panel performed its board reboot and USB/tty re-enumeration;
- the factory/default animation returned; and
- after re-enumeration, the user manually chose **Detect panel** and received
  the expected model, firmware 3.2, and 480×320 resolution.

This completes physical acceptance of Panel Control App v1. It does not qualify
the action as recovery for an already stalled or unresponsive panel, and it
does not authorize automatic reconnect, query, retry, reset, or recovery
behavior.

## Current limitations

- No other VID:PID, model, firmware, or geometry is claimed as supported.
- This is a local browser UI, not a packaged desktop binary.
- Closing only the browser tab does not stop the foreground launcher; use
  **Exit app** or `Ctrl+C` in the launcher terminal.
- The existing long-duration firmware 3.2 streaming-stall limitation remains;
  this milestone does not qualify or optimize sustained streaming.
- A confirmed stall can leave `/dev/ttyACM0` present while writes time out, and
  can then survive a controlled USB unbind/rebind. In the reproduced case the
  device remained in `lsusb`, the tty endpoint did not return, and Linux logged
  `can't set config #1, error -110`. Panel Control deliberately stops and shows
  an error; it must not mask this state with aggressive retries.
- Seeing the HONGTAI device in `lsusb` is not sufficient recovery evidence.
  After a stall, leave the app stopped. A full physical host/panel power-cycle
  followed by one bounded detection remains the qualified recovery procedure.
- The starter dashboard reuses existing lightweight Linux metrics. Panel
  Control v1 does not add sensor sources or extend the layout editor.
- Display Media Library v1 supports only one selected PNG/JPEG still at a time.
  It provides no animation, video, slideshow, file watching, remote media, or
  persistence of the selection between app sessions.
- Packaging, autostart, remote access, Windows, device-family expansion, and
  publication remain outside this milestone.

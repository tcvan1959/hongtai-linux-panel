# Bounded streaming diagnostics

Long-duration testing is suspended until the host's handling of panel replies
is understood. The public experimental InfoPanel implementation reads the
device-information response but does not read after JPEG uploads or `0x11`
commands. This project previously behaved the same way.

`hongtai-diagnose-stream` is a deliberately bounded evidence-gathering tool. It
does all of the following:

- disables reconnects;
- stops after 60 seconds by default and rejects durations above 1,800 seconds;
- sends a full dashboard JPEG every five seconds by default;
- keeps the live pipeline active with one-second refresh commands;
- checks the kernel's unread serial-byte count after each operation;
- drains available input so a reply queue cannot grow without observation;
- incrementally reassembles and checksum-validates framed replies;
- counts unframed or malformed bytes; and
- records frame, keepalive, JPEG-size, operation-latency, and low-level write
  measurements;
- uses an isolated 0.75-second per-write timeout rather than the general
  driver's five-second timeout;
- can fail-stop on tty disappearance or a new kernel USB/ACM event for an
  explicitly supplied physical USB path;
- returns a failing exit status on the first captured streaming error; and
- prints a bounded hexadecimal sample and aggregate summary when it stops.

The tool must not be run while the panel is stalled or before the user has
approved a physical test. A controlled unbind/rebind of the panel's USB path is
now known not to recover one reproduced stall: `lsusb` retained the device, the tty
did not return, and the kernel logged `can't set config #1, error -110`. Do not
repeat unbind/rebind, reset, reconnect, or query attempts. The previously
prepared command remains documented for provenance but is not authorized by
the successful power-cycle or exit test:

```bash
hongtai-diagnose-stream --duration 60 --frame-interval 5 --quality 55
```

## Completed recovery and exit test

A complete cold power-cycle restored the normal firmware animation and healthy
operation. On August 19, 2026, exactly one bounded exit-sequence test was then
performed and was not repeated:

```text
RESET -> 0x11 -> one verified JPEG -> FF D9 FF D9 -> 0x11
wait 3 seconds -> standalone FF D9 FF D9 -> 0x21 -> close
```

The JPEG displayed correctly, but the panel remained blank after close. This
rules out that combined sequence as a way to resume the default animation on
the verified firmware 3.2 unit. It does not justify probing region, filesystem,
media-upload, or unknown commands. At that point restart remained untested; the
separately authorized result below supersedes only that part of the boundary.

## Completed restart/default-display test

On August 20, 2026, command `0x01` (`CMD_RESTART`) was physically verified on
the `33c3:7802`, model `TXW818-ST7796-3.5inch-hor`, firmware 3.2 device. It
performed a board-level reboot, caused the expected USB disconnect and
re-enumeration, restored the factory/default animation, and returned as a
healthy serial device that accepted a device-information query.

This result establishes one reboot-based route out of the blank post-stream
state. It does not show that `0x21` resumes default playback, reveal where the
animation is stored, identify a non-reboot playback command, or qualify `0x01`
as recovery for the previously observed USB-level stalled state. Diagnostics
and applications must not automatically retry this command or follow it with
automatic reconnect, query, reset, or unbind/rebind behavior.

## Internal playback boundary

The verified device reports an internal filesystem of 4,096 blocks at 2,048
bytes each (8 MiB total), and its default animation is therefore plausibly
stored or generated locally. Public protocol research names `setRegion`
(`0x20`) and describes a UTF-8 region/config payload; some notes characterize
this as preset selection, but no inspected evidence shows it starting playback.
The family references also contain generic file error codes, but do not provide
a verified file-upload opcode or file format for this unit. No storage-writing
command will be guessed or tested without stronger protocol evidence.

The negative exit test and positive restart test do not distinguish whether the
default animation is a filesystem file, a region-selected preset, or a
firmware-embedded resource. Together they establish that a final terminator
plus `0x21` does not select or resume it, while a board reboot through `0x01`
does restore it.

### Read-only family-reference findings

The following evidence is useful for directing source research but is not a
protocol test plan:

- Public reverse engineering names `0x20` `setRegion` and gives it a UTF-8
  region/config string payload. No inspected source shows `0x20` being sent
  after `0x21`, or proves that it starts internal playback.
- An independent utility reports command `0x07` as a directory-list operation
  on a different 1920×462, firmware 2.2 Hongtai-family display. Its payload is
  a UTF-8 path (empty for root), and the reported JSON response contains
  `data.dir_list` entries with filename/type/size fields. This is not verified
  on `33c3:7802` firmware 3.2.
- The same secondary source identifies `/data/` and `/data/video/` as OEM-app
  path constants. Its file-read, file-write, and media-upload mechanisms are
  labeled unknown, likely, hypothetical, or experimental rather than confirmed.
- Public product material says the OEM Windows software can configure images,
  animated images, and video. That establishes product capability, not whether
  the default boot animation is a replaceable file or which command selects it.

No inspected primary or secondary source identifies a non-reboot command that
resumes the stored/default animation after live mode on the verified panel.
The verified `0x01` path restores it by rebooting the board. `0x20` and `0x07`
remain read-only research subjects only; neither is authorized for a physical
command test by these notes.

## Low-rate 10-minute reliability result

On August 19, 2026, one authorized run used firmware 3.2, quality 55, a full
dashboard JPEG every 10 seconds, and bare `0x11` keepalives every one second.
Reconnect, reset recovery, automatic restart, and post-run device queries were
disabled. The run reached its 600-second limit normally:

- elapsed duration: 600.263 seconds;
- 60 full JPEGs, ranging from 12,467 to 13,000 bytes;
- 539 bare keepalives and 721 successful low-level writes (772,022 bytes);
- no serial exception, timeout, reconnect, or malformed reply byte;
- low-level write median 0.0305 ms, p95 2.348 ms, maximum 14.293 ms;
- noninitial full-frame operation median 3.066 ms and maximum 3.416 ms;
- bare keepalive operation median 0.0567 ms and maximum 0.0897 ms;
- 61 valid `0x11` response frames (488 bytes total), with an eight-byte queue
  high-water mark; poll labels show where a reply was drained, not necessarily
  which earlier asynchronous operation caused it; and
- the same bus/device number, tty, stable by-id link, and cdc_acm identity were
  present afterward. The test-window kernel log contained no USB or ACM error.

Visual correctness was not observed during the run and must not be inferred
from successful writes. The observer did not directly watch live rendering,
and the physical panel was blank afterward. The result is therefore a transport/USB
stability pass only, not a visual display pass. No post-run device-information
query was sent because it would reset the pipeline and add traffic after the
clean session. This result supports only that this low-rate transport workload
completed one 10-minute host-side qualification without a stall; it does not
establish visible rendering, 30-minute, 60-minute, unattended, or general
firmware reliability. Longer qualification is deferred until one short run is
directly observed from streaming startup through completion.

## Visually observed 60-second low-rate result

On August 19, 2026, one follow-up run was performed with an observer watching the
physical panel continuously from streaming startup through completion. It used
the same quality-55 dashboard, a full JPEG every 10 seconds, a bare `0x11`
keepalive every second, no reconnect, and the diagnostic's 0.75-second
per-write fail-stop ceiling.

The run reached its 60-second boundary normally. It sent six JPEGs ranging
from 12,304 to 12,941 bytes, 54 bare keepalives, and 74 successful low-level
writes. There were no write errors or malformed response bytes; maximum write
latency was 13.742 ms. The USB device, tty, and stable by-id link remained
present afterward, and the test-window kernel log contained no entries.

The observer reported that the display looked good, updated every 10 seconds,
and went blank after the test ended. This is a visual display pass and transport/USB
pass for one 60-second session at the tested cadence. The blanking remains the
known live-pipeline timeout behavior. The result does not convert the earlier
10-minute run into a visual pass and does not authorize or establish a
30-minute qualification.

## Thirty-minute low-rate qualification

On August 19, 2026, exactly one authorized 30-minute session used the same
quality-55 dashboard, one full JPEG every 10 seconds, and one-second bare
`0x11` keepalives. Reconnect, automatic retry, reset, unbind/rebind, and system
configuration changes remained disabled. The diagnostic also checked tty
presence and new kernel events for the panel's USB path during the run.

The session reached its 1,800-second boundary normally:

- elapsed duration: 1,800.304 seconds;
- 180 full JPEGs, ranging from 12,301 to 13,050 bytes;
- 1,615 bare keepalives and 2,157 successful low-level writes totaling
  2,310,799 bytes;
- no serial exception, timeout, reconnect, malformed reply byte, tty loss, or
  panel-related kernel event;
- low-level write median 0.0204 ms, p95 2.316 ms, maximum 13.505 ms;
- noninitial frame-operation median 3.044 ms and maximum 4.369 ms;
- bare keepalive-operation median 0.0349 ms and maximum 0.0987 ms; and
- 181 valid `0x11` response frames, with an eight-byte queue high-water mark.

Afterward, the panel retained the same tty, stable by-id link, `cdc_acm`
identity, USB path, and initialization identity. The test-window kernel log
contained no panel-related USB or ACM event. The observer's final visual
report confirmed that the dashboard looked good throughout, continued
updating every 10 seconds, and showed no flicker or other visible change while
running. The screen went blank after the test ended, consistent with the known
live-pipeline timeout behavior. This is therefore a visual display pass and a
transport/USB stability pass for one 30-minute session at the tested cadence;
it does not prove longer, repeated, unattended, or general firmware
reliability.

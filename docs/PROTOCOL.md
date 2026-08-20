# Hongtai protocol notes

This document separates behavior verified on the `33c3:7802` test device from
broader family behavior described by public protocol research.

## Transport

- USB CDC ACM serial transport
- 2,000,000 baud
- 8 data bits, no parity, no flow control

## Command frame

```text
55 AA | length LE u16 | command u8 | payload | checksum LE u16
```

- `length` is the complete frame length: payload length plus seven bytes.
- `checksum` is the unsigned 16-bit sum of every preceding frame byte.
- Responses use the same outer frame.
- The device-information payload is UTF-8 JSON on a successful response.

For example, the payload-free `0x11` refresh command is
`55 AA 07 00 11 17 01`. Its checksum is `0x0117`. Some early public protocol
notes listed `0x0111`; direct byte summation and the successful physical test
both support `0x0117`.

Verified command opcodes used by this project:

| Opcode | Purpose | Current use |
| ---: | --- | --- |
| `0x01` | Board restart; restores factory/default display after reboot | Verified, manual one-shot only |
| `0x06` | Get device information | Implemented |
| `0x11` | Wake/refresh live-image pipeline | Implemented |
| `0x21` | Close/release live pipeline | Explicit opt-in |
| `0x03` | Set brightness (one-byte `0..100` payload) | Explicit opt-in |

The library intentionally does not expose firmware update, serial-number,
motor, or other device-mutating commands.

## Connection and query sequence

1. Open the serial endpoint at 2,000,000 baud.
2. Send `FF D9 FF D9 00 00 00 00` to reset the parser/pipeline.
3. Wait approximately 200 ms.
4. Send command `0x06`.
5. Read one complete framed response and validate its length and checksum.
6. Parse the response payload as UTF-8 JSON.

## Live JPEG sequence

1. Reset the parser/pipeline.
2. Send command `0x11`.
3. Build the image envelope:

   ```text
   JPEG size LE u32 | JPEG bytes | envelope checksum LE u16
   ```

4. The envelope checksum is the unsigned 16-bit sum of the size field and JPEG.
5. Write the envelope.
6. Write `FF D9 FF D9` as the frame terminator.
7. Send command `0x11` approximately every 1.4–1.5 seconds while holding a
   static frame, or send subsequent frames for animation.

The verified firmware requires another `0x11` immediately after the terminator
to commit and reveal the uploaded frame. Without that post-upload refresh, the
next cycle's leading `0x11` revealed the prior frame only until the following
JPEG upload began. This produced a brief flash followed by a longer dark
period. The working first-frame sequence is therefore:

```text
0x11 | JPEG envelope | FF D9 FF D9 | 0x11
```

Once the live pipeline is awake, subsequent experimental frames omit the
leading refresh and use `JPEG envelope | terminator | 0x11`. This preserves one
refresh per frame while placing it where firmware 3.2 commits the new image.
These protocol units are written consecutively. A 100 ms delay before the JPEG
made the visible flash longer, but did not solve the missing commit.

The verified firmware clears the displayed live frame shortly after the serial
connection and refresh commands stop. A persistent background process is
therefore required even for a static image. Dynamic rendering now separates
these lightweight refreshes from full JPEG uploads: refreshes continue every
second, while the default dashboard image cadence is five seconds.

## Live-mode exit

Public family research describes both a standalone `FF D9 FF D9` live-stop
signal and command `0x21` as a close/release operation. One bounded test on the
verified firmware 3.2 panel sent both after a successfully displayed frame:

```text
reset | 0x11 | JPEG envelope | FF D9 FF D9 | 0x11
wait 3 seconds | FF D9 FF D9 | 0x21 | close serial port
```

The panel remained blank. Therefore, the combined standalone terminator and
`0x21` sequence is not a verified transition back to the default internal
animation on `33c3:7802`. No resume-internal-playback opcode is presently known,
and no media, region, or filesystem command should be inferred from this
negative result.

## Verified restart and default-display restoration

On August 20, 2026, command `0x01` (`CMD_RESTART`) was physically verified on
the `33c3:7802`, model `TXW818-ST7796-3.5inch-hor`, firmware 3.2 panel. Its
payload-free frame is:

```text
55 AA 07 00 01 07 01
```

The command caused a board-level reboot, including USB disconnect and
re-enumeration. The factory/default animation returned, and the re-enumerated
serial device was healthy and queryable. This observed USB lifecycle rules out
interpreting `0x01` as only an ST7796 display-controller reset on this unit.

`0x01` is therefore a verified reboot-based way to restore the default display,
but it is not a normal live-mode close and does not identify the internal
animation's storage or selection mechanism. A caller must send it at most once,
expect its current serial handle to become invalid, and leave any later detect
or query to an explicit user action. Automatic retry, reconnect, reset, or
unbind/rebind behavior is not qualified.

The presently documented JPEG safety limit is 80 KiB. This needs additional
device-specific testing before it should be generalized to every model.

## Video implications

Video can be represented as a sequence of resized JPEG frames over the live
pipeline. Practical frame rate will depend on compressed frame size, serial
overhead, firmware decoding speed, and whether frames may be sent continuously
without separate refresh commands. A later milestone will measure these limits
on the verified device before the application presents video as a supported
feature.

## Failure policy

Dynamic streaming defaults to fail-stop operation. A serial write timeout ends
the process cleanly and leaves recovery to the user rather than repeatedly
opening a firmware controller that may already be unresponsive. Automatic
reconnect is an explicit configuration choice, not the default.

The corrected one-refresh-per-frame sequence remained visually stable for
approximately 16 minutes at one full JPEG per second before a write timeout.
The process stopped without retrying, but the panel became blank and Ubuntu's
serial device node disappeared while stale USB and CDC ACM records remained in
sysfs. The next qualification therefore uses one full JPEG every five seconds
with intervening refresh-only keepalives. Automatic startup remains disabled.

That reduced-load qualification lasted approximately 49 minutes before the
same write timeout and blank display. This time the serial device remained
enumerated and the kernel recorded no USB disconnect or driver error. Reducing
the frame rate therefore extended runtime but did not eliminate the failure.
Long-running dynamic mode remains experimental; automatic startup must stay
disabled until a different strategy is qualified.

The failure was also reproduced with `/dev/ttyACM0` still present when serial
writes began timing out. A single controlled unbind/rebind of physical USB path
the panel's USB path did not recover it: `lsusb` still listed the HONGTAI device,
`/dev/ttyACM0` was no longer created after rebind, and the kernel logged
`usb <bus-port>: can't set config #1, error -110`. The defect is therefore
confirmed
to reach the USB configuration/device-firmware level and can survive driver
unbind/rebind. Presence in `lsusb` must not be treated as proof that the panel
is usable.

The required response remains fail-stop. Do not add aggressive open, write,
reconnect, reset, or unbind/rebind loops. A one-shot `0x01` restart is verified
on a healthy, responsive firmware 3.2 panel as a manual return to the default
display; it has not been qualified as recovery for an already stalled or
unresponsive device and must not be triggered automatically.

The public experimental implementation reads the response to `0x06` but does
not inspect serial input after live JPEG uploads or refresh commands. This
project originally had the same blind spot. A bounded diagnostic now records
the kernel input-queue depth and drains, reassembles, and validates any returned
frames after every live operation. Whether unconsumed replies caused the stalls
remains a hypothesis until the recovered panel completes that diagnostic.

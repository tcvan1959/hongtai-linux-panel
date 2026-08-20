# Protocol and implementation provenance

Copyright 2026 Timothy C. VanDeventer.

This repository is licensed under Apache-2.0. Its Python, JavaScript, HTML,
CSS, JSON, tests, and documentation are independently written for this project.
A pre-publication comparison found no copied or substantially adapted
implementation code from the GPL reference described below. Protocol command
numbers, packet layouts, checksums, response fields, and observed device
behavior are recorded as interoperability facts, not incorporated upstream
source code.

## Independently verified hardware facts

The project began with physical investigation of one Hongtai panel exposed on
Linux as `33c3:7802` / `HONGTAI MONITOR`, model
`TXW818-ST7796-3.5inch-hor`, firmware 3.2, resolution 480×320. The facts marked
verified in this repository were exercised on that unit, including device-info
querying, live JPEG display, keepalives, brightness, blank-after-stop behavior,
the bounded low-rate dashboard runs, the USB/firmware stall, cold-power
recovery, and the one-shot `0x01` board restart that restores the factory
animation. The individual unit's UID and USB serial are intentionally not
published.

These results do not establish compatibility with other Hongtai/Jungle Leopard
models or firmware versions. They also do not prove unattended or general
long-duration reliability.

## InfoPanel GPL-3.0 reference

Protocol research was informed by the public InfoPanel Jungle Leopard/Hongtai
work. The inspected revision was commit
`39ac3d4d886713cbf67da94f2a2b84ab24af89fe` from the `jl-panel-support`
work, accessed August 20, 2026:

- repository and declared GPL-3.0 license:
  <https://github.com/emaspa/infopanel-1>
- support change and complete changed-file list:
  <https://github.com/habibrehmansg/infopanel/pull/140/files>
- protocol notes: `JL-PROTOCOL.md`
- protocol-bearing C# implementation:
  `InfoPanel/JlPanel/JlSerialDevice.cs`

InfoPanel's documentation and implementation were used to identify candidate
wire-format facts for independent implementation and testing. GPL
implementation code is not incorporated in this repository. Any future plan
to copy or adapt InfoPanel code requires a separate licensing and attribution
review before work begins.

## Independent `jungle-leopard` MIT reference

The independent utility <https://github.com/nickadam/jungle-leopard> was also
inspected at commit `64694502a0c7d3c236a2f89efcfec20cf30bd4f6`, accessed
August 20, 2026. Its `LICENSE` declares the MIT License, copyright 2026 Nick
Vissari. The relevant research material was `main.go` and its observations
about command `0x07`, directory responses, and family-level paths such as
`/data/` and `/data/video/`.

No source code from that utility is incorporated here. Its directory and path
findings concern a different 1920×462, firmware 2.2 family device and are not
verified on this project's 480×320 firmware 3.2 panel. Its experimental or
hypothetical file-transfer observations are not treated as protocol commands
for this device.

## OEM application and product claims

InfoPanel and the independent utility report reverse engineering of the
proprietary OEM Windows application, identified in the InfoPanel notes as
`Jungle Leopard Display.exe` version 1.0.52. This project did not incorporate
or redistribute that application, its code, or its assets. Statements about
what the OEM application sends are indirect upstream reports unless separately
marked as physically verified here.

Public product claims that the Windows software configures images, animated
images, or video establish family-level advertised capability only. They do
not establish the storage layout, upload format, preset selection, or playback
command for the verified panel.

## Evidence labels

Documentation in this repository uses these boundaries:

- **Physically verified:** observed on the `33c3:7802`, firmware 3.2 unit.
- **Protocol fact:** a wire value or structure supported by interoperable
  implementations and, where stated, local testing.
- **Family-level reference:** reported for another Hongtai/Jungle Leopard
  device and not assumed to apply to this model.
- **Indirect OEM observation:** reported by upstream reverse engineering, not
  independently obtained from OEM source.
- **Hypothesis or speculation:** a possible interpretation that must not be
  converted into a device command without stronger evidence and separate
  authorization.

No inspected source identifies a verified non-reboot command that resumes the
factory animation after live streaming on this panel. The `0x20` region command
and `0x07` directory operation remain research evidence, not authorized
physical tests.

## External dependencies

Pillow is an optional external image dependency and setuptools is an external
build dependency. Neither is vendored or bundled in this source tree. No
third-party JavaScript, fonts, images, or media assets are included. If a
future binary distribution bundles dependencies, their applicable license
texts and notices must be reviewed for that distribution.

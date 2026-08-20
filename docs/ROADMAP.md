# Development roadmap

## Milestone 1 — protocol baseline

- [x] Pure command-frame and checksum implementation
- [x] Validated device-information parsing
- [x] Serial connection and query tool
- [x] Static-image conversion and transmission tool
- [x] Hardware-independent protocol tests
- [x] Repeat device-information query on the physical panel from the package
- [x] Transmit the built-in static test pattern through the packaged command
- [x] Accept Linux Direct Panel Driver v1 with a correct 10-second physical
  orientation/rendering run and clean timed shutdown (August 18, 2026)
- [x] Verify clean `Ctrl+C` shutdown and serial closure on the test host

## Panel Control App v1

- [x] Reuse the loopback-only editor server and visual language
- [x] Detect and identify the verified panel through the accepted driver
- [x] Start and stop one foreground streaming worker cleanly
- [x] Apply validated brightness changes through the streaming owner
- [x] Preview and select the orientation test or starter dashboard
- [x] Show explicit disconnected, detected, streaming, stopped, and error state
- [x] Add the confirmed, one-shot Restore default display panel-restart action
  with no automatic reconnect, query, or retry
- [x] Add hardware-independent controller and loopback HTTP tests
- [x] Complete the bounded test-host GUI acceptance procedure, including the
  one-shot restore action, USB re-enumeration, factory-animation restoration,
  and manual post-restart detection (August 20, 2026)
- [x] Record the reproduced USB-level firmware stall and failed single
  unbind/rebind recovery (`can't set config #1, error -110`)
- [x] Test recovery through a full physical host/panel power-cycle, then run
  exactly one bounded detection/query
- [x] Verify one healthy-panel `0x01` board restart restores the default
  animation and returns through USB re-enumeration

## Pre-publication freeze and baseline planning

- [x] Enter feature freeze after Panel Control App v1 physical acceptance
- [x] Plan the first intentional Git baseline without creating it implicitly
- [x] Audit repository contents, provenance, licensing, secrets, generated
  artifacts, documentation consistency, and GitHub readiness
- [x] Review audit findings before configuring a remote, creating the first
  commit, or publishing anything

Later feature milestones below are parked during this freeze and are not the
next authorized work.

## Display Media Library v1

- [x] Add separate public-sample and Git-ignored local/private media concepts
- [x] Select direct-child PNG/JPEG files from `display_media/local/`
- [x] Browse another local PNG/JPEG without copying it into the repository
- [x] Preview a selection without automatically starting the panel stream
- [x] Preserve aspect ratio with a safe 480×320 center fit and JPEG encoding
- [x] Display through the existing foreground worker and retain Stop/restore
  behavior
- [x] Reject GIF, animation, video, corrupt, missing, unreadable, and unsafe
  inputs without adding remote or automated media features
- [x] Verify software behavior and package exclusion with automated tests and
  source/wheel inspection
- [x] Complete one bounded, visually observed physical acceptance sequence
  using an external private PNG (August 20, 2026; asset not retained)

## Milestone 2 — experimental display-service research (outside accepted v1)

- [x] Device discovery using `/dev/serial/by-id`
- [x] Automatic disconnect/reconnect implementation (unsupported and disabled
  by default; not physically qualified)
- [x] Physical foreground-service startup with automatic device discovery
- [ ] Physical USB disconnect/reconnect exercise
- [x] Continuous one-frame-at-a-time dashboard rendering
- Bounded producer/consumer frame queue for higher-rate media
- Brightness and orientation controls after device-specific validation
- [x] Versioned, validated configuration file
- [x] Previewable user-level service installer (not accepted v1)
- [x] Earlier physical handoff to an automatic-login service; subsequently
  disabled and not qualified as supported behavior
- [ ] Re-enable automatic startup after dynamic protocol stability is re-qualified
- [x] Persist firmware-safe fail-stop behavior as the configuration default
- Structured logs and useful error messages

## Milestone 3 — dashboard research

- [x] CPU load, memory, and clock sources
- [x] CPU temperature through Linux hardware-monitoring interfaces
- [x] NVIDIA GPU telemetry with graceful AMD fallback
- Storage and network sources
- Text, image, bar, gauge, graph, and status widgets
- [x] Fixed starter dashboard for the verified 480×320 device
- [ ] Long-duration live updates on physical firmware 3.2 (one-second full
  frames failed safely at about 16 minutes; five-second full frames with
  one-second keepalives failed safely at about 49 minutes)
- [x] Qualify one visually observed 30-minute session at 10-second quality-55
  full frames with one-second keepalives; this is not unattended qualification

## Milestone 4 — visual editor

- [x] Versioned declarative layout and widget model
- [x] Generic renderer for panels, labels, clocks, values, bars, and images
- [x] Safe live reload with last-known-good fallback
- [x] 480×320 preview canvas
- [x] Drag, resize, duplicate, delete, and configure widgets
- [x] Layer ordering and single-widget canvas alignment controls
- Multi-widget selection and alignment controls
- Save and switch dashboard profiles
- Choose fonts, colors, backgrounds, and refresh rates
- Accessible defaults and recovery from invalid layouts

## Milestone 5 — animation and video

- Benchmark sustainable JPEG sizes and frame rates
- Animated image playback
- Video decoding, scaling, pacing, and frame dropping
- Clear device capability reporting rather than assuming every panel performs
  identically

## Milestone 6 — broader device support

- Runtime geometry and firmware capability profiles
- Compatibility table backed by repeatable reports
- Packaging and installation instructions for common Linux distributions
- Public repository publication after local review

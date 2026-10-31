---
title: "ESP32-P4 DJ deck: beat sync over Pro DJ Link, with rekordbox's beat grids"
date: 2026-10-31T12:00:00-07:00
tags: esp32, dj, pro dj link, rekordbox, embedded, audio
---

Two days ago I [measured how much CPU the ESP32-P4 deck had left](/blog/posts/esp32-p4-deck-status.html), so I'd know whether Pro DJ Link would fit. Today it went in. The deck joins the network as a player, finds the tempo master, and with SYNC on it locks to the master's beat. It uses the beat grid rekordbox already worked out for the track, so the deck doesn't analyse anything itself. In steady state it holds the beat to within about 1.4 ms of the master.

This post covers how it's built, the numbers, and the detours. There were a lot of detours.

## What "beat sync" needs

To play in time with another player, a deck needs three things:

1. **The master's tempo and beat timing.** Pioneer players broadcast both on Pro DJ Link. Each playing deck sends a beat packet on every beat, and a status packet about five times a second that says, among other things, whether it's the tempo master.
2. **Where the beats are in our own track.** That's the beat grid.
3. **A way to steer playback** so our beats land on the master's.

## Reusing the packet layer from freedj-3000

[freedj-3000](/blog/posts/cloning-an-xdj-1000.html), my XDJ-1000 clone in Rust, already speaks Pro DJ Link. Its packet layouts were checked byte by byte against a real XDJ-1000MK2 and against prolink-cpp's virtual CDJ, and both captures are pinned as tests. I ported that layer to C++ for the P4.

That includes the status packet. Rather than build one from scratch, freedj copies a status packet captured from the XDJ and overwrites only the fields it understands. Every byte nobody has documented is therefore exactly what Pioneer firmware sends. freedj found the hard way that this matters: one wrong byte made the XDJ refuse to hand over tempo master. The P4 uses the same template.

On the deck it's one small task on core 0, next to the UI. It announces itself as player 2 every 1.5 s and sends its status to every other player five times a second. It listens for everyone else's beats and status. That costs 2–4 % of core 0.

## Reading rekordbox's beat grid without its database

A rekordbox USB stick has two kinds of analysis data. One is `export.pdb`, the database of tracks and playlists, in a page-based format that takes real work to parse. The other is a folder of per-track analysis files, `PIONEER/USBANLZ/…/ANLZ0000.DAT`, one per track.

The shortcut: each `ANLZ` file holds the path of its own audio file (a `PPTH` section) as well as the beat grid (a `PQTZ` section). So the deck can list every analysed track and find its grid by walking the analysis folder, without touching the database. The grid itself is simple: for every beat, its time in milliseconds, the tempo, and its position in the bar (1–4).

The reader is about 150 lines of plain C++. I tested it on the PC first, against the demo export that ships with the `rekordcrate` library. It gave 128 BPM, beats 469 ms apart, and correct bar positions. On my own stick it found 218 analysed tracks.

## Steering the deck onto the beat

SYNC does three things:

- **Match the tempo.** Our speed is the master's BPM divided by our track's BPM at the playhead. If half or double time is closer, it uses that, so a 70 BPM track plays at 1× against a 140 BPM master.
- **Snap on PLAY.** When you press play with SYNC on, the deck first jumps so its first beat lands on the master's. Nothing is audible yet, so the jump is silent.
- **Hold the phase.** On every 5.8 ms audio block, the deck compares where it is in its beat with where the master is in its beat, and bends the tempo by up to 3 % to close the gap. A CDJ nudges the same way when you touch the jog wheel.

"Where it is in its beat" has to mean what's coming out of the speaker *now*, not where the playhead is. About 35 ms of audio is queued between the audio task and the DAC. In keylock, the time-stretcher holds some audio of its own too. The deck subtracts both.

## The numbers

These were measured against prolink-cpp's virtual CDJ running on my PC as master at 128 BPM:

| | Phase error vs master, avg / worst |
|---|---|
| A rekordbox track, from the first 2 s after PLAY | 1.4 / 3.3 ms |
| Same, keylock on, after a few seconds | 2.6–3.7 / 9–11 ms |
| SYNC switched on mid-track | snaps, then 1.4 / 3 ms |

Audio stayed at 100 % real time throughout.

One caveat: those numbers compare the deck against its own timing model, not against what you'd hear. The model assumes a beat packet arrives at the moment that beat is heard on the master, and the keylock delay is an estimate. Both need checking by ear against a real XDJ. There's a serial key to trim the offset 2 ms at a time for that.

## Bugs along the way

**A crash on the first packet.** The deck rebooted as soon as the virtual CDJ appeared. I had written a "new player" log line inside a spinlock. ESP-IDF's logging takes a lock of its own, and that isn't allowed with interrupts off. The fix was to note the new player inside the lock and print it after.

**A six-second catch-up at the start of a track.** The snap on PLAY often wanted to jump to a point slightly *before* 0:00, so it got clamped to the start. The deck then started up to half a beat off and needed six seconds of tempo bending to recover. Now it jumps to the next beat instead.

**Keylock chasing a sawtooth.** In keylock, the error sat around 6 ms and wouldn't settle. The time-stretcher is fed in 512-frame chunks, so my estimate of how much audio it was holding jumped up and down in steps. The controller was correcting noise it had made itself. Smoothing the estimate over about 0.3 s brought it down to roughly 3 ms.

**224 tracks, 2 KB of RAM.** With the stick's tracks in the list, the board had 2 KB of internal RAM left and couldn't load anything. Every list row is an LVGL button and a label, and every small allocation was landing in internal RAM. I moved LVGL's allocations to PSRAM, and that freed the memory. It also dropped the waveform from 46 to 34 fps and slowed the audio core, because LVGL also allocates small blocks for every frame it draws. Now only the track list goes to PSRAM, built once at boot, and the board has 80 KB free.

## Hardware detours

**Ethernet.** The link came up at 100 Mbit and dropped again 2–4 s later, over and over. My setup matched Waveshare's own Ethernet example exactly, so I asked for a different cable. The new cable fixed it.

**The USB ports.** The board has four USB-A ports, but only one worked. The schematic explains why. A jumper, H3, drives a USB switch that connects either a 4-port hub or one port wired straight to the chip. My board was in the single-port setting, and the DJ2Go was in that port. Swapping the stick into that port got it working. Moving the jumper didn't help: in both positions only that one port works, and the hub never shows up. So for now it's either the DJ2Go or the stick, not both. I haven't found the cause yet.

## What isn't right yet

- **The waveform is slower than before.** It used to run at 46 fps. It's now 34–41 fps while playing a track from the stick, with core 0 at 42–48 % instead of about 30 %. It isn't the allocator. It could be the USB stick: its interrupts land on core 0, where the SD card's didn't. It could be the longer list. I haven't pinned it down.
- **One keylock block took 5.1 ms of its 5.8 ms budget** while a track was still loading. Nothing dropped out, but that's too close, and it's the first thing to look at next.
- **Boot takes longer:** reading 218 analysis files adds 6.9 s. Caching the list on the stick would fix that.
- **Not tested with a real XDJ yet.** That will also show whether other players see the deck properly.

## Next

- Test against the XDJ-1000MK2, and tune the timing by ear.
- Find where the frame rate went, and get keylock's worst block back down.
- Send beat packets too, so the deck can be tempo master and other players can sync to it.
- Find out why the hub never appears, so the DJ2Go and the stick can both be plugged in.

The code is in [audiodestrukt/esp32-mediaplayer](https://github.com/audiodestrukt/esp32-mediaplayer) under `p4/deck`.

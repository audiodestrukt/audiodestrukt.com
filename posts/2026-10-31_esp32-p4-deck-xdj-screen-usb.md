---
title: "ESP32-P4 DJ deck: an XDJ-style screen, a lying frame counter, and four USB ports that were really three"
date: 2026-10-31T22:00:00-07:00
tags: esp32, dj, rekordbox, pro dj link, embedded, usb, debugging
---

This morning the deck could [beat-sync to other players over Pro DJ Link](/blog/posts/esp32-p4-deck-beat-sync.html). The rest of the day went into making it look and behave more like an XDJ-1000, and finding out how much of the ESP32-P4 that leaves free. The goal is to get as close to an XDJ as this chip allows, so every feature now comes with a measurement.

Here's what got built, the bugs it turned up, and the USB hardware puzzle that took most of the afternoon.

## Looking like an XDJ

**Phase meter.** The XDJ has a strip above the waveform with two views, and you switch between them by touching it. My Rust XDJ clone, [freedj-3000](/blog/posts/cloning-an-xdj-1000.html), had already worked both out from photos of the real unit:

- **Beat display:** two rows of four boxes. The top row lights the bar within the 4-bar phrase, the bottom row the beat within the bar.
- **Alignment view:** the master's beats on one row and ours on another, scrolling under a fixed playhead. If the decks drift, you see the rows slide apart.

Both rows come from data we already had: the master's beat packets from Pro DJ Link, and our own beat grid.

**Beat grid on the waveform.** It shows a short tick per beat, and a longer red one on each bar's first beat. It's cheap, because the ticks are drawn into the waveform canvas that's redrawn every frame anyway. It's also useful even when rekordbox's grid is right: it's how you see that two tracks line up, and how you spot the one track rekordbox got wrong.

**Track overview with needle search.** The thin progress bar became an overview of the whole track. Touch or drag it to jump there. The deck doesn't analyse anything for this. rekordbox stores a 400-column preview waveform in each track's analysis file, next to the beat grid, so the deck reads it at load and draws it once. After that it redraws only when the playhead moves a pixel, so it costs nothing measurable.

## The frame counter was lying

I'd been quoting the waveform at 46 fps for days. When I added the phase meter, the alignment view seemed to be running at 90 fps, which made no sense over a 40 MHz SPI link.

The counter was counting how often the waveform got *redrawn*, not how often a frame actually reached the screen. LVGL merges several redraws into one frame when it can, so the counter read high. The fix was to count LVGL's "frame rendered and sent" event instead. The real number with everything on screen is about **38–42 fps**.

That also changed the story I'd been telling about a frame-rate "drop" from 46 to 34. It was at least partly the counter. Since then, every change that moves the numbers goes into a changelog with the measured budget: per-core CPU, the worst audio block, real fps and internal RAM. That way I can see what each feature cost.

Where the budget stands now, playing a rekordbox track from the stick, synced, with everything on screen:

| | |
|---|---|
| Core 0 (screen, loader, USB, network) | ~48 % |
| Core 1 (audio only) | 11 % (varispeed), ~28 % (keylock) |
| Screen | 38 fps |
| Internal RAM | 102 KB free, 80 KB at its lowest |

Internal RAM is the tightest resource, and two of today's bugs were about it.

## Two crashes, both from running out of the wrong RAM

**224 tracks, 2 KB free.** The first time the list held a whole rekordbox stick, the board had 2 KB of internal RAM left and couldn't load anything. Every list row is an LVGL button and a label, and every small allocation lands in internal RAM by default.

Moving all of LVGL's memory to PSRAM freed the RAM, but it cost about a quarter of the frame rate and slowed the audio core as well. LVGL also allocates small blocks for every frame it draws, and putting those in PSRAM meant more PSRAM traffic, the same contention that [slows keylock when the waveform scrolls](/blog/posts/esp32-p4-deck-status.html). In the end only the list rows go to PSRAM, and later the list's strings too.

**Loading a track reset the board.** A heap assert, "block already marked as free". The backtrace went through the USB stick driver. While minimp3 builds its seek index, FAT reads a big run of the file, and the driver grows its DMA buffer to about 32 KB for it. The largest free block of internal RAM was 31 KB, so the allocation failed. The driver had already freed the old buffer, and on the error path it freed it again. The fix was an ESP-IDF option that puts USB transfer buffers in PSRAM, which the P4's USB DMA can reach.

## Needle search found a hidden half-second

The first needle jump into a track left 0.53 s of silence. I timed the steps: the MP3 seek itself took 530 ms, and during that "seek" minimp3 **read 5.3 MB of the file**.

The rekordbox-exported MP3s carry a VBR info tag. When minimp3 sees one, it takes the length from the tag and puts off building its seek index until the first seek away from the start. So the index got built mid-performance, on the first jump. Tracks without the tag had always been indexed at load, which is why I hadn't seen it.

Building the index at load fixed it. The jump gap is now 46 ms, and sync re-snaps onto the master's beat once audio is there.

Two smaller fixes came out of the same test:
- **Loader pacing.** After a jump, the loader refilled all 70 s of its window at full speed and held core 0 at 100 % (the screen dropped to 9 fps). Now it decodes at full speed only until 8 s are buffered, then paces the rest.
- **Sync after a stall.** The deck now waits until audio exists at the new spot before snapping to the master, and re-snaps after any stall. Before, the master kept going while we sat in the gap, and the tempo bend took four seconds to catch up.

## Four USB ports, three of which work

The board has four USB-A sockets. For most of the day, only one worked, and the DJ2Go was in it.

**The jumper.** The schematic shows a jumper driving a USB switch chip. The switch connects the P4's one USB port either to a socket wired straight to the chip, or to a CH334F 4-port hub. The hub's fourth port goes to two test pads, not a socket. So it's three hub sockets *or* the direct socket, never all four. The labels on the jumper are also the wrong way round: the hub is on the side marked DEVICE.

**The hub, and the missing translator.** With the hub on, the stick worked, but the DJ2Go didn't:

```
E HUB: Connected device is FS, transaction translator (TT) is not supported
```

The DJ2Go is a full-speed (USB 1.1) device. Behind a high-speed hub, the hub has to translate, and ESP-IDF's USB host doesn't implement that. Espressif's answer in their [issue tracker](https://github.com/espressif/esp-idf/issues/17245), from July, is that it isn't a priority and there's no timeline.

The workaround, which I found in [espp's usb_host component](https://components.espressif.com/components/espp/usb_host), is to limit the P4's root port to full speed. Setting one bit in the USB controller's config register makes the hub itself run at full speed, and then every device behind it is reached directly. The bit has to be set again periodically, because the controller clears it whenever it recovers the port.

It works. The DJ2Go and the stick now run side by side. The cost is that the stick runs at 12 Mbit/s too:
- **Playback** doesn't care.
- **The boot scan** of 218 analysis files went from 7 to 13 s.
- **An MP3 load** went from 0.5 s to 5 s, because building the seek index reads the whole file.

## Not waiting for USB, and pulling the stick mid-track

A 13-second scan at boot wasn't acceptable, so the deck no longer waits for it. The screen comes up at **3.8 s** with the SD tracks. The stick is read in the background with a "Reading USB stick…" notice, and its tracks join the list when the read is done.

That needed a track list that can change while the deck runs, which also made **hot-swapping sticks** possible:
- **The list** is an immutable snapshot that gets replaced whole, so the audio task, the loader and the screen never see one half-built.
- **Load requests** carry the file path instead of a list position that might have moved.
- **The selection** follows its track across list changes.
- **Pulling the stick** cancels the scan, drops its tracks, and closes the open file before the stick is unmounted.

Moving the list's strings to PSRAM also took internal RAM at boot from 68 to 112 KB free.

And since about 70 seconds of the current track are already decoded in PSRAM: **if you pull the stick while its track is playing, the deck goes into an emergency loop**, as a CDJ does. It loops 4 beats from the beat grid out of memory, shows E.LOOP, and reports the CDJ's emergency-loop play state to the other players. Because the loop is a whole number of beats, sync holds: 1.4 ms through the loop in the test.

## What's next

- **Loads are about 5 s from the stick** at the slower USB speed. The fix is to build the MP3 index in the background once the track is ready to play.
- **The track list could be cached on the stick**, so it doesn't have to be re-read every time.
- **Cues and loops from rekordbox's analysis files.** That brings the XDJ's "Bars" countdown to life too.
- **The real XDJ-1000MK2 test**, by ear.

The code is in [audiodestrukt/esp32-mediaplayer](https://github.com/audiodestrukt/esp32-mediaplayer) under `p4/deck`. The changelog there now has the resource budget at every step.

---
title: "ESP32-P4 DJ deck: where it stands, and how much CPU is left"
date: 2026-10-30T12:00:00-07:00
tags: esp32, dj, embedded, audio, benchmarks
---

Yesterday I wrote about [the waveform stealing my audio](/blog/posts/esp32-deck-waveform-starved-the-dac.html). Since then the deck has gotten faster, lighter on the CPU, and it no longer lies about loudness when keylock is on. This is the status report with numbers. The point is to know how much room is left before I add Pro DJ Link, which is the next big thing.

## Where it is

The hardware is a Waveshare ESP32-P4 dev kit: two RISC-V cores at 360 MHz and 32 MB of PSRAM. A Numark DJ2Go plugs into its USB host port. A 4" 480×320 SPI touch screen sits on jumper wires as a stand-in for the DSI screen I'm waiting on. Audio goes out the board's own codec to a small speaker.

What works today:

- **Tracks.** WAV and MP3 from the SD card, streamed through a 12 MB window in PSRAM (about 71 s around the playhead). MP3 seeks land on exact samples because the file is indexed when it loads.
- **Pitch.** Varispeed (±8 %, pitch follows speed, like a turntable) and keylock (time-stretched, pitch stays put).
- **Controls.** CDJ-style CUE (tap to return, hold to preview), jog nudge and scrub. The DJ2Go, the touch screen and serial-port keys all drive it.
- **Screen.** A scrolling waveform with the playhead in the middle, the track list, time, tempo, and a progress bar with the cue point.

The earlier timecode vinyl version on the ESP32-A1S still builds from the same repo, and the two share code. I'm keeping it working.

## How it performs

Every number here comes from the deck itself. Every 2 s it prints a health report: real-time %, audio block timing, a click detector, and CPU per core and per task. A script on the PC drove the run over the serial port: load, play, toggle keylock, switch the waveform off, and so on. That way each phase measures the same thing.

| Playing `house.mp3` (256 kbps, 2:15) | Core 0 | Core 1 (audio) | Waveform | Audio block, avg / max |
|---|---|---|---|---|
| Varispeed, waveform scrolling | 31 % | 8 % | 46 fps | 0.43 / 0.88 ms |
| Keylock, waveform scrolling | 31 % | 30 % | 46 fps | 1.75 / 3.1 ms |
| Keylock, waveform off | 12 % | 17 % | — | 0.94 / 1.8 ms |

- **Real-time was 100.0 % in every 2-second window** of the run. No dropouts, in any mode.
- **The audio budget is 5.8 ms per block** (256 frames at 44.1 kHz). The worst block in the whole run used 4.1 ms, at the moment keylock switched on. In steady state keylock peaks around 3 ms.
- **The click detector reads zero on `sine.wav`** in both varispeed and keylock. That's the test where it's exact. On music it counts drum hits as well, so I don't read it there. The sine file is only 2 s long, so a longer tone test is still to do.
- **The waveform runs at 45–47 fps.** I was hoping for 30.

Other numbers:

| | |
|---|---|
| Power on to UI ready | 2.0 s |
| Load an MP3 (2:15, 256 kbps) to PLAY ready | 0.65 s (0.57 s of it is the seek index) |
| Load a WAV | 0.13 s |
| Free memory while playing | 173 KB internal RAM, 19 MB PSRAM |
| Firmware size | 1.14 MB (24 % of the app partition free) |

## How much is left

**Core 1 is audio and nothing else.** The worst case is keylock with the waveform up, at about 30 %, which leaves 70 %. Varispeed uses 8 %.

**Core 0 runs everything else** (UI, SD loader, USB, the reporter) and sits around 30 % with the waveform scrolling, so about 70 % is free. That's where Pro DJ Link will go. The protocol traffic itself is light: beat packets, status every 200 ms, a handful of UDP sockets. The heavy part, later, would be serving tracks to other players. If that ever gets tight, capping the waveform at 30 fps gives back another ~8 % of core 0.

Two days ago it looked very different. With the waveform up, core 0 was at 98 % and core 1 at 42 %, and the audio was running at 80 % speed. Three fixes got it here:

1. **The DAC's interrupt was on the wrong core.** That's the [previous post](/blog/posts/esp32-deck-waveform-starved-the-dac.html).
2. **LVGL busy-waited on every SPI transfer.** Its default "is the frame sent yet?" check is `while (flushing);`, which pins a core for as long as the transfer takes, about 40 times a second. A wait callback that sleeps on a semaphore, woken by the transfer-done interrupt, cut core 0 from 98 % to 62 %.
3. **The touch interrupt was firing constantly.** The per-task breakdown showed the FreeRTOS timer task using about 25 % of a core, but only while the waveform scrolled. On jumper wires, the 40 MHz SPI clock couples into the touch controller's interrupt wire. Every false edge woke the UI through an event group, and ESP-IDF handles those from an interrupt via the timer task. The UI already polls touch every 30 ms, so I turned the interrupt off. Core 0 went to 30 % and core 1 to 8 %. Touch still works.

None of these fixes made anything faster. They stopped the chip doing work that didn't need doing. And none of them would have been found without the per-task numbers.

## One thing the numbers show that I didn't expect

Keylock costs about twice as much CPU while the waveform scrolls: 1.75 ms per block with it on, 0.94 ms with it off. The keylock code doesn't change between those two runs, and it runs alone on core 1. What changes is core 0 pushing a 96 KB frame through PSRAM 46 times a second. The two cores share the PSRAM bus and the L2 cache, so core 1 waits longer for its data. There's plenty of headroom, so it doesn't matter yet. It's worth knowing before the network stack shows up on core 0.

## Why keylock sounded louder and brighter

While testing, I noticed that switching keylock on made the music brighter and louder. A time-stretcher should change speed and nothing else, so that's a bug.

The keylock is WSOLA (waveform-similarity overlap-add). It slices the audio into 1024-sample windows, picks each next slice where it lines up best with the last one, fades each slice with a Hann window, and overlaps them at a 256-sample hop. That's 75 % overlap, so every output sample is the sum of four faded slices. Four Hann windows at 75 % overlap add up to **2.0**, not 1.0. The code never divided that out.

I measured it on the PC, since the same WSOLA code builds there, by putting a loud house track through it at 1.0×:

| | Level | Clipped samples |
|---|---|---|
| Input | — | 92 |
| Keylock, before | **+5.5 dB** | **790,825** (~13 % of all samples) |
| Keylock, fixed | **0.0 dB** | 8 |

So keylock played the track about 6 dB hot. On a mastered track that is already near full scale, that pushed about one sample in eight into the 16-bit ceiling. Hard clipping adds harmonics, which is exactly "brighter". The fix scales each window by ½. It also switches to the "periodic" form of the Hann window, which overlaps to an exactly flat 1.0 at 75 %.

The bug has been in the A1S firmware the whole time too, since they share this file. On the A1S, keylock is the default mode for timecode vinyl, and I had already capped the DAC volume there to fight crosstalk from the output back into the timecode input. I suspect those 6 extra dB were part of why that cap was needed. That one needs testing on the A1S with real vinyl before I believe it.

## What's next

- **Pro DJ Link** over the board's Ethernet, on core 0.
- **Deck B and a crossfader.**
- **An overview waveform,** with the analysis cached on the SD card so each track is only analysed once.
- **A real stereo DAC** (PCM5102A) and a line-in ADC (PCM1808) for timecode on this board.
- **The DSI screen.** It has proper vsync. The SPI stand-in has none: the ST7796S controller has a tearing-effect pin, but the module doesn't bring it out.

The code is in [audiodestrukt/esp32-mediaplayer](https://github.com/audiodestrukt/esp32-mediaplayer) under `p4/deck`. The README there has the wiring, the task layout, and what each number in the health report means.

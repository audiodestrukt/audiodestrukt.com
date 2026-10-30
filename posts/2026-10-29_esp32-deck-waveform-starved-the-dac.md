---
title: "The waveform was stealing my audio: debugging an ESP32-P4 DJ deck"
date: 2026-10-29T20:00:00-07:00
tags: esp32, dj, embedded, audio, debugging
---

I've been building a small CDJ-style deck on an ESP32. This week I added a scrolling waveform, and the music immediately started playing slow and glitchy. The fix turned out to be a single line. Finding it was the interesting part, so this post is about how we tracked it down, including the two times I was confidently wrong.

## The deck

This started years ago as a retrofit for a Numark mini turntable: timecode vinyl for control and a two-line LCD for picking songs. It has since turned into a little CDJ replacement on a Waveshare ESP32-P4 dev kit:

- **Processor.** The P4 has two RISC-V cores at 360 MHz, 32 MB of PSRAM, and four USB-A ports on a real USB host.
- **Controls.** A Numark DJ2Go plugs straight into one of those USB ports and stands in for the control panel I haven't built yet. The MIDI mapping is shared with my Rust player, [freedj-3000](/blog/posts/cloning-an-xdj-1000.html).
- **Audio.** It goes out through the board's ES8311 codec to a tiny speaker. Fine for development, useless for hearing clicks, which matters later.
- **Tracks.** WAV and MP3 stream from the SD card through a 12 MB window in PSRAM, about 71 seconds of audio around the playhead. Jog, cue and short seeks are instant.
- **Screen.** A 4" 480×320 SPI module with capacitive touch (ST7796S plus FT6336U), wired to the 40-pin header with jumper wires while I wait for the proper DSI screen. LVGL draws the UI.

The layout is simple. Audio gets core 1 to itself. Core 0 runs everything else: the SD loader, USB, and the UI.

## The symptom

The waveform is the CDJ-style view: the playhead stays fixed in the middle and the track scrolls past it. The loader already decodes every sample, so I had it keep one peak byte for every 128 frames as it goes. The UI draws from that array into a canvas and never touches the audio itself. Cheap on paper.

On the device, as soon as the waveform appeared the music slowed down and started to stutter. The time counter on the same screen updates constantly and never caused a problem. Only the waveform did.

## Wrong turn one: "no dropouts"

Earlier that day the browse beep had been sounding like a double tick. To check for dropouts I hooked up the I2S driver's "send queue overflow" callback, which is supposed to fire when the DAC runs out of data. I scrolled through the track list 160 times and it never fired. I concluded the audio path was clean and blamed the beep's sharp edges.

That counter never fired once, in any test, including the ones where the audio was plainly broken. A counter that is always zero shows you nothing about whether the audio is fine. I took the beeps out anyway (a DJ deck shouldn't make its own noises), but the conclusion was wrong.

## Measuring the right thing

The speaker is too small to hear pops, so we built measurements instead:

1. **Real-time percentage.** Count the frames handed to the DAC and compare them with the frames it must have played in the same wall-clock time. Anything under 100% means gaps of silence, however the driver feels about it.
2. **Block work time.** How long the audio task takes to compute each 256-frame block, against a budget of 5.8 ms.
3. **Click detector.** On the exact samples going to the DAC, track the second difference (how sharply the slope changes) and flag spikes far above its running average. On a test tone it is exact. On music, drum hits set it off.

The first numbers:

| | Real-time | Block work |
|---|---|---|
| Idle (silence) | 99.9 % | ~0 ms |
| Playing, waveform up | **78–80 %** | 0.46 ms avg, budget 5.8 ms |

So the deck was delivering about four fifths of the audio, which explains both the slowness and the stutter. And it wasn't a CPU problem: the audio code used under a tenth of its budget. The time was going into waiting on the DAC. Each write waited longer than the audio it handed over.

## Wrong turn two: the cache

The P4's two cores share an L2 cache, and the build was still at debug optimisation. My theory was that the UI was pushing the audio code out of the shared cache. So I built with `-O2` and doubled the L2 cache to 256 KB.

Nothing changed: still around 78%. A reasonable theory that the measurement ruled out in one run.

## Bisecting from the serial port

At this point every experiment meant: flash, walk over, load a track, press play, wait, tell me what happened. Too slow. So I added serial keys to the firmware: digits select a track, `l` loads, `p` plays, `c` cues. There's also `w`, which steps the waveform through three test modes. A logger on the PC holds the port open and passes keys through, so the whole experiment could run without anyone touching the deck.

`w` was the decisive one:

| Waveform mode | Real-time | Waveform fps |
|---|---|---|
| Drawn and sent to the screen | 80 % | 20 |
| Drawn, **not** sent to the screen | **99.7 %** | 160 |
| Off | 99.4 % | — |

Drawing cost nothing: 160 fps of drawing into PSRAM and the audio didn't notice. Sending the result to the screen is what broke it. That's also why the time counter was harmless. A few changed digits is a small SPI transfer. The waveform is about 96 KB per frame, twenty times a second.

While this was running, I asked whether the DAC was competing with the screen for TX/RX. On the wires, no: the screen has its own SPI pins. Inside the chip, yes. And it pointed at the real question: what do the DAC and the screen actually share?

## The one line

In ESP-IDF, a driver's interrupt is allocated on the core of whatever task installs the driver. I had initialised audio from `app_main`, which runs on core 0. So the audio *task* was on core 1, but the I2S *interrupt* was on core 0, competing with LVGL and a steady stream of SPI DMA completions from the screen.

The fix was to move `audio_out::begin()` into the audio task itself, so the I2S interrupt lands on core 1 with the code it serves. Startup now waits on a semaphore, because the touch chip shares the codec's I2C bus.

| | Real-time | Block work | Min slack | Waveform |
|---|---|---|---|---|
| Before | 78–80 % | 0.46 ms | 0.0 ms | 20 fps |
| After | **100.0 %** | 0.43 ms | 4.5 ms | 18–19 fps |

`sine.wav`, where the click detector is exact, shows zero clicks. That's a short file, so a longer tone test is still to do.

I'll be honest about one gap. I can show *where* the problem was and that moving the interrupt fixes it. I can't fully explain *why* a delayed interrupt costs a steady 20% of throughput rather than an occasional glitch. My guess is that DMA buffers are refilled late and the hardware plays them out without a gap-free hand-off. It's a guess, and I'll leave it as one until I've traced it.

## One more catch from the same numbers

The block-work maximum sat at 9.5 ms, over the 5.8 ms budget, even after the fix. The culprit was my own status line: the audio task printed two log lines every two seconds over a 115200-baud UART, and that takes longer than an audio block. The DAC buffer was absorbing it, but printing from the audio loop is a bug waiting to happen. Now the audio task fills a small report struct and a low-priority task on core 0 prints it. The max dropped to 0.75 ms.

## What I'm taking from it

- **Measure delivery, not driver events.** "Frames sent vs frames owed" is one line of arithmetic and it can't lie the way an event counter can.
- **Know where your interrupts live.** Pinning a task to a core says nothing about where its driver's interrupt runs.
- **Make the device drivable.** The serial keys turned a walk-over-and-press-play loop into a script, and that's what made bisecting possible.
- **Write down the wrong turns.** Both of mine were plausible, and both were ruled out by a number in under a minute.

The code is in [audiodestrukt/esp32-mediaplayer](https://github.com/audiodestrukt/esp32-mediaplayer) under `p4/deck`. Next up: a faster SPI clock for the waveform, deck B, and fixing keylock on 48 kHz tracks. The timecode vinyl mode still works through all of this, and I mean to keep it that way.

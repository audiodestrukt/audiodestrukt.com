---
title: "Is an $80 Raspberry Pi faster than an XDJ-1000?"
date: 2026-10-14T10:00:00-07:00
tags: opendeck, dj, pro dj link, rust, raspberry pi, benchmarks
image: images/2026-10-14_pi-vs-xdj-1000-performance_meta.png
---

Last week I wrote about [cloning the XDJ-1000MK2](/blog/posts/cloning-an-xdj-1000.html) and getting the clone to run on a Raspberry Pi 5. Since then the thing I keep noticing is not that the clone works. It is that the clone feels quicker than the deck it copies. The waveform is steadier, tracks come up faster, and CUE lands where my finger lands.

My first explanation was the lazy one: it's written in Rust, Rust is fast. That is partly true and mostly not the reason, and "feels quicker" is not a number. So this post is the scorecard. Some rows are measured on both machines. Some are measured on mine and still open on the XDJ, with the procedure I am going to use written down so the numbers come out comparable. I will fill the open cells in as I get them and update this page.

![The XDJ-1000MK2 screen next to OpenDeck's, same track, same layout](images/2026-10-14_pi-vs-xdj-1000-performance_meta.png)

## The scorecard

Both machines play the same 5:13 MP3 at 44.1 kHz, pitch at 0 %. "OpenDeck" is the Pi 5 unless the cell says otherwise. The full table with methods lives in the repo as [hardware-comparison.md](https://github.com/audiodestrukt/freedj-3000/blob/main/docs/reference/hardware-comparison.md).

| What | XDJ-1000MK2 | OpenDeck |
|---|---|---|
| Beat packet timing (jitter at one receiver) | 1.33 ms | 1.23 ms (desktop build) |
| Waveform scroll | Visible flicker while playing | 60 fps, 0.12 ms frame jitter, no dropped frames |
| Track load to PLAY ready | **[XDJ: measure]** | 0.7 s on the Pi 5, from scratch; 0.5 s on the desktop |
| Power on to ready | **[XDJ: measure]** | 0.9 s app start to first frame (desktop); OS boot not counted |
| CUE press to sound | **[XDJ: measure]** | A few ms to the seek; end-to-end at the jack **[measure]** |
| CPU while playing | Not visible from outside | About 0.6 of one core, three cores idle |
| Price | [€1,299 at launch, 2016](https://djworx.com/pioneer-dj-xdj-1000mk2/) | $80 board plus a screen |

The honest summary: on the one row measured head to head it is a tie. On the screen it is a clear win for the clone and I have not yet put a number on the XDJ's side. Everything else is mine to measure.

## The tie: beat timing

Pro DJ Link players broadcast a packet on every beat. Another deck syncing to you follows those packets, so how evenly they arrive is the one performance number that other people's gear can see. In August I captured both players' beat packets at the same receiver in the same run, with both decks playing at 0 %, and took the standard deviation of the interval between beats.

The XDJ came out at 1.33 ms, mine at 1.23 ms. That is not a win, that is the same number with noise on it. The XDJ has been doing this for a decade and does it well. Mine gets there by free-running a phase-locked clock off the audio position and sleeping to a deadline for the last 1.5 ms before each send. The desktop produced that number; the Pi's is still to come.

## The win: the screen

Put the two screens side by side with the same track and the XDJ's waveform flickers slightly as it scrolls. Not broken, just a little unsteady, the way a display looks when the thing drawing it can't quite keep up with the thing it is drawing. I am not the only one who sees it. A [2018 review on the DJ TechTools forum](https://forum.djtechtools.com/showthread.php?t=95424) put it as "Low refresh frequency display makes for laggy interface/waveform."

The Pi's waveform does not do that, and the reason is where the work happens. The whole track's waveform lives in a GPU storage buffer. Scrolling it is one number, the playhead position, handed to the shader once a frame. Nothing is re-uploaded, nothing is re-analysed, nothing is blitted. The playhead itself is phase-locked to the display: it advances by whole display periods read from the monitor, and the frame is drawn from the compositor's own callback, so a frame is never early or late with respect to the thing that will show it. On the Pi 5 that measures as 60 frames a second with a frame-to-frame jitter of 0.12 ms and no stalls in the sample. The Pi's display stack came out tighter than my NVIDIA desktop, which surprised me.

What I have not done is measure the XDJ's screen in frames per second. The procedure is simple and I will do it: film both screens at 240 fps with a phone, step through one second of frames, count how many distinct waveform positions appear. Until then the XDJ cell says "flicker" and not a number.

## Loading, with an asterisk

This one needs the asterisk up front. When the XDJ loads a track from a USB stick it reads an analysis rekordbox already did on a laptop: the beat grid, the waveform, the cues. It does not analyse anything. OpenDeck decodes the file and analyses it from scratch on load, waveform and BPM included, unless it has seen the track before. So "load time" means different work on each machine.

Even so, the number DJs feel is the same on both: press LOAD, wait for PLAY to be ready. On the Pi 5 the whole thing for a 5:13 MP3 is 0.7 s, decode included. On the desktop it is 0.5 s cold and 0.4 s with the grid cached. That is measured from the log, and it is the lower bound; the procedure for the XDJ, filming the screen from the press to the drawn waveform, will give both machines the same stopwatch.

For context, when Pioneer launched the CDJ-3000 [the headline was its new processor](https://www.attackmagazine.com/news/pioneer-dj-introduces-the-mpu-powered-cdj-3000/), and the thing they said it bought was faster track and cue loading, replacing what the trade press called the DSP-based design of the previous generation. Loading on the older decks was slow enough that fixing it was the pitch for a $2,400 player. I do not know what is inside the XDJ-1000MK2 and I have not opened it. I only know what the screen does.

## CUE

The thing that made me want to write this at all. On a deck, CUE is the button you hit on the beat, so the gap between your finger and the sound is the whole instrument. In the clone every press goes through a small state machine with written specs, the seek is applied while the deck is paused so the next press finds the cursor already at the cue, and the processor waits for the output to drain before it pushes the first block after a seek, so the transient you cued is heard and not thrown away. There is a 3 ms fade on stop to kill the click and deliberately no fade on start. From the press to the seek being applied is a few milliseconds; the rest is the audio device's buffer.

I do not have the XDJ's number. Getting it is a two-channel recording: a small mic taped next to the CUE button, so the tact switch's click is the time reference, and the line out on the other channel, a cue set on a kick, ten presses, measure click to kick in a DAW. Same rig on the Pi with the DJ2Go's pad, and on the iPad with a stylus. I expect the device buffer to dominate on both and I expect them to be close. That is the honest expectation; the point of measuring is that I might be wrong.

## Is it Rust?

A bit. Rust gives this project no garbage collector, no runtime pauses, and threads I can split without fear: the audio thread, the loader, the Link listeners and the renderer are all separate and none of them can corrupt the others' data. The audio callback never allocates. That is real and it is why the engine was easy to make glitch-free.

But the board is seven years newer than the deck. The Pi 5 is four Cortex-A76 cores and a GPU with a real Vulkan driver, and the architecture leans on that GPU for the one thing a deck screen does all day. If I had written the same design in C it would be about as fast. If I had written the XDJ's design in Rust on the XDJ's hardware it would not be. Rust made the right architecture cheap to build on a $80 board; it did not make the board.

## Where the XDJ wins

A real jog wheel on a real bearing, with a capacitive top and a sensor that reports exactly where your hand is. Real buttons, each a tact switch with a click you feel. Boot into a known state every time. Ten years of firmware decisions about what a deck should do when you do something strange. rekordbox and the stick in your pocket that works in every booth in the world. None of that is on the scorecard because none of it is a number, and the clone does not have it. The Pi needs a screen, a mouse or a MIDI controller, and an active cooler, and it is a deck in the sense that it does what a deck does, not in the sense that you would carry it to a gig.

## What's next on the table

In order: film both screens and put a frames-per-second number in the waveform row; film both loads; do the two-channel CUE recording; and run the beat-timing capture again with the Pi sending instead of the desktop. Each one replaces a bold cell above. If any of them goes the XDJ's way, the row will say so.

The clone is on the App Store as [OpenDeck DJ](https://apps.apple.com/app/id6807472453), the source is at [github.com/audiodestrukt/freedj-3000](https://github.com/audiodestrukt/freedj-3000) under the GPL, and the Pi build instructions are in the repo. XDJ, CDJ, rekordbox and Pro DJ Link are AlphaTheta's names; this project is not affiliated with them.

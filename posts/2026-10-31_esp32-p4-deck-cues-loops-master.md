---
title: "ESP32-P4 DJ deck: cues, loops, slip, and becoming the tempo master"
date: 2026-10-31T23:30:00-07:00
tags: esp32, dj, pro dj link, rekordbox, embedded, audio
---

After [the screen and USB work](/blog/posts/esp32-p4-deck-xdj-screen-usb.html), I listed what the deck still needs for XDJ-1000 parity and put it in order. First on the list was the performance basics: cues, loops, beat jump, quantize, slip, reverse. Second was being a full Pro DJ Link player, which means sending beats and being able to take tempo master. This post covers both. Most of it turned out to be logic, not per-sample DSP, which is why it fit in a day.

## One idea under all of it: whole beats

Nearly every feature here comes down to moving the playhead without upsetting the beat. The deck already had the pieces:

- rekordbox's **beat grid**, which converts between track time and beats
- the **sync controller**, which measures our phase against the master's every 5.8 ms audio block

The rule that ties it together is **quantize**, on by default as on the XDJ:

- Cue, hot cue and loop points snap to the nearest beat.
- Every jump lands at the *same point within the beat* as where you left.

So a hot cue pressed 30 % of the way through a beat lands 30 % of the way through the target beat. The music never stumbles, and when the deck is synced the master never sees a phase slip. I used the sync phase error as the test: it stayed at **1.4 ms average** through every loop, halve, double, exit, hot cue jump, beat jump and manual loop.

## Cues and loops

**Hot cues and memory cues come from rekordbox.** They live in the same per-track analysis files as the beat grid, in two formats: the classic cue list in the `.DAT` file, and an extended one with colours and comments in the `.EXT` file next to it. Newer rekordbox versions often fill only the extended one, so the deck reads that first. As on a CDJ, a track loads at its first memory cue.

None of my test tracks had cues, so I checked the parser against a synthetic `.EXT` built by hand from rekordcrate's layout before trusting it.

**Loops:**
- beat loops of 1–16 beats
- manual in/out, on the DJ2Go's small LOOP IN / LOOP OUT buttons
- reloop/exit, halve/double
- beat jump ±4, which moves an active loop along with it, as on the XDJ

The emergency loop from the last post, which kicks in when the stick is pulled mid-track, now uses the same loop engine.

**Slip** keeps a shadow playhead running at normal speed during a loop, reverse or held hot cue. When you let go, playback picks up where the track would have been, and a grey line on the waveform shows where that is. Slip through a 6-second loop resumed exactly 6 seconds further on, still in phase with the master.

**Reverse** always plays without keylock. The time-stretcher (WSOLA) only runs forwards, and at normal tempo you can't hear the difference.

**Tempo range** follows the XDJ: ±6, ±10 (the default now), ±16 and WIDE (±100 %), with tempo reset.

All of it is on a PADS panel on the touch screen, standing in for the XDJ's PERFORM screen:
- all eight hot cues
- CALL ◀ ▶ through the memory cues, MEM / DEL
- loop /2 and x2, RELOOP, SLIP
- beat loops 1–16, beat jump, REV

The "Bars" countdowns next to the phase meter finally show something. They count bars and beats to the next memory cue and the next hot cue, as on the XDJ.

## Being the master

Until now the deck could only *follow*. A Pro DJ Link player also has to talk.

**Beat packets.** Every playing player broadcasts a packet on each beat. Ours goes out when the beat is *heard*: the audio task already knows the heard position (the playhead minus about 35 ms of DMA queue), so it predicts when the next beat will reach the speaker, and the network task sends right then.

The first version sent only every other beat. The audio task updates "next beat" every 23 ms, and if the network task woke a moment after the audio had already moved on to the following beat, the due beat was skipped. Now the network task holds on to the beat it's waiting for until it's sent.

Over 33 beats at 126 BPM, the average interval was 0.4762 s, exactly right, with 5.3 ms of jitter as received on the PC. The beat-in-bar count stays correct through loops too.

**Taking master** follows the handshake [freedj-3000](/blog/posts/cloning-an-xdj-1000.html) worked out against a real XDJ-1000MK2:
1. Ask the current master for the role (packet 0x26).
2. It agrees to yield (0x27).
3. Wait until its status *names you* as its successor, then claim.

Claiming on step 2 alone made the XDJ abort the handoff, so the wait matters. The deck handles the other direction too: it yields when asked, and lets go once the new master claims. Another player can also switch our SYNC on or off remotely.

To test it, I ran prolink-cpp's virtual CDJ on the PC in `--follow-master` mode at 120 BPM. The deck took master, the virtual CDJ reported itself synced, moved to our 126 BPM, and put its beats within about ±15 ms of ours.

**Mixer integration** is in, but untested: the on-air flag and fader start from a Pioneer DJM, from Deep Symmetry's protocol notes. I don't have a DJM, so it's marked untested in the docs.

## Two testing traps

**The listener that ate the reply.** For a while the virtual CDJ ignored our master requests completely. The deck was fine: a hand-built packet from the PC got through. The problem was my test rig. I had prolink-cpp's packet listener running on the PC too, sharing port 50001 with the virtual CDJ. For a unicast packet, Linux picks *one* of the sockets sharing a port, so our requests were going to the listener. With the listener stopped, the handoff worked first time.

**Two copies of every beat.** The PC is on the same network over both Ethernet and Wi-Fi, so it receives each broadcast twice, a few tens of milliseconds apart. It looked like the deck was double-sending until I checked the interfaces.

## Where the budget stands

All of this is logic, so the audio core barely noticed:

| Playing a stick track, synced, loop + hot cue, waveform up | |
|---|---|
| Core 1 (audio) | 12 % (varispeed) |
| Core 0 (screen, loader, network) | ~48 % steady, ~60 % while the buffer refills |
| Link task | 2–4 % of core 0 |
| Internal RAM | 79 KB at its lowest |
| Sync | 1.4 ms average |

## What's next

- **The real test:** the XDJ-1000MK2. Sync both ways, master handoff both ways, and trimming the phase by ear.
- **The rest of Link:** loading tracks from another player's stick, and letting it load from ours. That's the heavy part, a network file server plus rekordbox's database, and it gets its own session.
- **rekordbox's track database**, for proper browsing by playlist, artist and key.
- **Colour waveforms.**

The code and the changelog, with the resource budget at every step, are in [audiodestrukt/esp32-mediaplayer](https://github.com/audiodestrukt/esp32-mediaplayer) under `p4/deck`.

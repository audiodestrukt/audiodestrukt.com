---
title: "freedj plays stems now, from a USB format someone else was kind enough to publish"
date: 2026-11-10T12:00:00-08:00
tags: opendeck, dj, rust, stems, audio, testing
image: images/2026-11-10_freedj-stems_cdj-volume.png
---

[OverCue](https://overcue.gg/) is a free, unofficial mod for the CDJ-3000, made by three DJs. Its headline feature is stems: you run your rekordbox stick through their desktop app, it splits each track into **drums**, **vocal** and **harmonics** (everything else), and the modded player lets you mute or blend them live.

The part that got my attention is that they published the stick format. The stems live in a `CDJMODS` folder beside the rekordbox export, and the layout is written up as an [open, MIT-licensed spec](https://github.com/OverCue-gg/overcue-stems-format), along with a small validator. The README says outright that another player can read the same files and use its own controls and audio path.

So [freedj](https://github.com/audiodestrukt/freedj-3000) does that now. Put in a stick prepared by OverCue Desktop, turn stems on, and the tracks on it play with their stems.

![freedj's CDJ-3000 screen with the STEMS panel open in VOLUME mode: drums at 60 %, vocal 35 %, harmonics 75 %](images/2026-11-10_freedj-stems_cdj-volume.png)

## Off unless you turn it on

A stock XDJ-1000MK2 or CDJ-3000 has no stems, and I want freedj's screens to stay what the real units are. So stems are a row in MENU / UTILITY, **STEMS**, off by default. Off, nothing changes anywhere: no extra keys, no stems loaded.

![The UTILITY list with the new STEMS row switched on](images/2026-11-10_freedj-stems_menu.png)

Turned on, each skin gets its controls:

- **CDJ-3000 screen:** a STEMS key next to BEAT LOOP. It opens a panel in the same row the BEAT LOOP and BEAT JUMP panels use, laid out the way OverCue's manual describes its own: FULL MIX, a TOGGLE / VOLUME switch, then the three stems. In TOGGLE a tap mutes a stem. In VOLUME each stem becomes a fader you drag, and a drag moves the level from where it already is, so touching it never makes it jump. The key greys out while stems load or when a track has none, and gets a blue underline while the mix is changed and the panel is closed.

![TOGGLE mode with the drums muted](images/2026-11-10_freedj-stems_cdj-toggle.png)

- **XDJ screen:** the XDJ has no spare spot on its playback screen, but freedj already has a PERFORM page of its own, with pads for hot cues and beat jumps. STEMS adds a third pad mode there: DRUMS, VOCAL, HARMONICS and FULL MIX. Tap a pad to mute it, drag up or down to set its level.

![The XDJ skin's PERFORM page in STEMS mode](images/2026-11-10_freedj-stems_xdj-perform.png)

## One stretcher, not three

The obvious way to play three stems is three of everything, including three time-stretchers for Master Tempo. That's the expensive part of a deck, and on a Raspberry Pi it's already most of the CPU.

freedj doesn't do that. It adds the stems together, at their levels, *before* the time-stretcher, so there's still exactly one. Mixing costs three multiply-adds per sample. And when every stem is at full, the deck plays the original track untouched, not the three stems added back up. FULL MIX gives you the real master, with none of the small artefacts that splitting a track always leaves.

The cost of that choice is latency: a mute only reaches your ears after it has gone through the stretcher and the output buffer. With the default stretcher I measured 70 to 120 ms from the tap to the change in the audio. That's fine for muting a vocal over a phrase, but not for chopping drums on the beat. I want to measure the other stretchers before deciding whether it needs work.

## Lining them up: measure, don't trust

Stems are only useful if they line up with the track to the sample. Otherwise turning one off and on smears the transients. OverCue's spec is careful about this. Its app pads the stems so they match how a CDJ-3000 decodes the original, and it warns that other players have to check alignment against their own decoder.

So freedj doesn't trust the padding. When a track loads, it cross-correlates OverCue's copy of the full mix with its own decode at three points in the track:

- All three have to agree within one sample, and correlate strongly, or the stems are refused and the original just keeps playing.
- The same happens if the music file no longer matches the hash OverCue recorded, say after a re-export from rekordbox.

On my first real run, the three measurements agreed on an offset of **1152 samples**. That's exactly one MP3 frame, the same metadata frame that the spec's own changelog spends a paragraph on, because different decoders keep or drop it. Trusting the padding would have played the stems 26 ms late.

## Testing it without a prepared stick

I don't have a stick prepared by OverCue yet. Their desktop app is Mac and Windows only, and I tried running the Windows build under Wine. It installs. Its window is a web view, and it came up black: the bundled Microsoft WebView2 crashes under Wine. With an older WebView2 from Microsoft's update catalog the window got further, then the app crashed inside Wine's drag-and-drop code. That's a Wine bug, not theirs. The Mac will have to do it.

In the meantime the tests build their own sticks. freedj's stems crate has a small writer for the format, used only in tests, and I checked its output with OverCue's own validator in every variant: FLAC pages, the older zlib pages, the 44.1 kHz profiles, and the compact per-track index. All accepted. So the reader is tested against files the reference tool calls valid, and every hash and offset in the spec is checked before any audio plays.

For the end-to-end run I used one of my own tracks and made stand-in stems: split into three frequency bands that add back up exactly, with "drums" as everything under 200 Hz. Then freedj ran with no window or speakers, recording its own output while a script muted drums, restored the full mix, and soloed drums:

![A spectrogram of freedj's output: the low band vanishes when drums are muted, returns with the full mix, and plays alone at the end](images/2026-11-10_freedj-stems_spectrogram.png)

The low band vanishes on the first line, comes back unchanged with FULL MIX, and plays alone at the end. You can also see the delay: each change lands a little after its line.

## What's next

- **A real prepared stick.** Everything so far has used stand-in stems, so real separated stems from OverCue Desktop are the first thing to try.
- **The waveform.** OverCue redraws the big waveform from the stems you're playing. freedj's still shows the full mix.
- **Stems over Pro DJ Link.** Loading a track from another player's stick and streaming its stems over the network, page by page, ahead of the playhead.
- **Hardware controls.** Stem actions for MIDI controllers and the hardware deck.

The plan and the measurements are in [stems-overcue.md](https://github.com/audiodestrukt/freedj-3000/blob/main/docs/design/stems-overcue.md), and the reader is the `stems` crate in [audiodestrukt/freedj-3000](https://github.com/audiodestrukt/freedj-3000). Thanks to the OverCue folks for writing the format down. It's the reason this took days and not months.

*freedj-3000 and OpenDeck are independent projects, not affiliated with or endorsed by AlphaTheta, Pioneer DJ or OverCue. CDJ-3000, XDJ-1000MK2 and rekordbox are AlphaTheta's trademarks, and OverCue is its authors', named here to describe compatibility.*

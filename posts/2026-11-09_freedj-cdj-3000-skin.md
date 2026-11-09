---
title: "My XDJ clone grew a CDJ-3000 screen, and the two grid keys that don't light when you'd think"
date: 2026-11-09T09:00:00-08:00
tags: opendeck, dj, rust, pro dj link, rekordbox, testing
image: images/2026-11-09_freedj-cdj-3000_loop.png
---

[freedj-3000](/blog/posts/cloning-an-xdj-1000.html) started as a copy of the XDJ-1000MK2: same screen, same behaviour, a Pro DJ Link player like any other. This week it got a second face. In MENU there's now a **SCREEN** row: XDJ-1000MK2, as before, or **CDJ-3000**. Switch it mid-set and nothing is lost, because both screens draw the same deck and send the same actions.

![freedj's CDJ-3000 screen with the BEAT LOOP panel open and a 4-beat loop running](images/2026-11-09_freedj-cdj-3000_loop.png)

This post is about how the screen was built, the two buttons that took a test rig to understand, and what writing the tests afterwards turned up.

## Measured against the unit

Every element was built by putting freedj next to an emulated CDJ-3000 showing the same state, then measuring the CDJ's screen in pixels:

- **Sizes and colours:** row heights, key sizes, gaps, colours.
- **Behaviour:** what lights when, what a tap does.

When the measurements disagreed with the manual, the measurements won. Page 2 of the BEAT LOOP panel isn't in the manual at all: it's 3/4, 1, 3/2, 3, 5, 6, 7 and 9 beats. The waveform zoom came from counting pixels: 18 px per beat at 128 BPM, which makes the CDJ's view 5.3 times as wide as the XDJ's.

What's in so far:

- **Playback:** the CDJ's waveform look (amber loop shading, no grid lines inside the wave), the BEAT LOOP and BEAT JUMP panels with both pages, the INFO overlay, and cover art from the track's tags.
- **SOURCE:** your local folder, each USB stick and each Pro DJ Link player, with the player number as a badge. The source the loaded track came from is green and marked "Loaded".
- **LOAD PREVIOUS TRACK:** the CDJ's pop-up list of what you played before, newest first.
- **rekordbox sticks:** the CDJ's category column (ARTIST, ALBUM, TRACK, KEY, PLAYLIST, HISTORY, FOLDER), and tracks as a table with BPM and KEY columns and each track's small preview waveform, read from rekordbox's own analysis files. Tracks you've played this session turn green, like on the unit.
- **SEARCH:** the on-screen keyboard. On a rekordbox stick it matches title or artist, and in a plain folder it matches file names anywhere below. On a computer you can just type.

![SEARCH with the on-screen keyboard: "ALO" finds ALOTT and Galo](images/2026-11-09_freedj-cdj-3000_search.png)

## Two grid keys that don't light when you'd think

Long-press the rotary on a CDJ-3000 and the waveform's panel row becomes GRID ADJUST: SNAP GRID, SHIFT GRID, two half-beat nudges and RESET. I built the row, and then noticed that on the emulated unit SNAP GRID stayed dim no matter what I did.

![GRID ADJUST on freedj: SNAP GRID and SHIFT GRID dim, the half-beat nudges lit](images/2026-11-09_freedj-cdj-3000_grid.png)

**SNAP GRID** puts beat 1 on your cue point. The manual says it needs an analysed track, so I tried a stick exported from rekordbox. It was still dim. The difference turned out to be the cue, not the track: SNAP only lights once you've *set a cue yourself* (pause somewhere, press CUE). The cue the deck places when a track loads doesn't count. After that it stays lit, even after you snap.

**SHIFT GRID** was stranger. On a CDJ, when you're synced and you nudge the jog because the beats aren't quite on top of each other, the CDJ *keeps* that offset. It stays synced, just a little off the master's beat, exactly where you put it. SHIFT GRID then writes that offset into the track's grid, so that next time sync alone lines it up. So it only lights while the deck is synced and holding a nudge.

To see that, the emulated CDJ needed something to sync to, and I used freedj itself. I gave the two a private network segment of their own on one machine, made freedj the tempo master, and nudged the CDJ's jog while it was synced. SHIFT lit up. A nudge forward and straight back moved the grid by nothing. One big nudge moved it most of a beat.

That also showed freedj had it backwards. Its sync pulled the phase back onto the master's beat on every beat, so a nudge while synced just vanished, and SHIFT GRID would have had nothing to work with. Now it leaves the phase alone while you nudge and holds wherever you leave it.

There's an automated test for this now (`make test-shift-grid`). It makes the emulated CDJ the master, runs freedj synced to it from a script, and reads freedj's own phase measurement on every beat. The checks:

- **Before the nudge:** freedj is on the beat.
- **After the nudge:** it holds the offset it was given. On a passing run that was +0.069 of a beat, not pulled back to zero.
- **After SHIFT GRID:** it's back on the beat straight away, within 0.02 of a beat, with no jump in what you hear.

One loose end remains. On the CDJ, nudging forward and nudging back both moved its grid the same way on screen. The size always matched the nudge, so my best guess is that it wraps the offset within one beat. A quarter beat late is the same grid as three quarters early. I haven't proven it yet.

## What the test caught on its first run

The first time that end-to-end test ran, sync never locked at all. The phase slid about 0.075 of a beat every beat, steadily and in one direction, which is what two clocks running at different speeds look like.

They were. The test track was 48 kHz and the audio device runs at 44.1 kHz. Tracks loaded from the browser were already converted, but the track freedj opens at startup wasn't. And because the first track set the deck's rate, every track loaded after it was converted to the wrong rate too. The whole session played 8 % slow, about a semitone and a half flat. On its own you might not notice; synced to a CDJ there's no hiding it. The startup track now gets converted like every other load.

## Then I went looking for missing tests

After a lot of new screens in a short time, I went back through everything from the last few sessions and asked what would break silently. The app's test count went from 102 to 117, and the tests found two more bugs:

- **Every converted track was about 21 ms too long.** The resampler pads its last block with silence. That's harmless to hear, but wrong. The new test checks a 1 kHz tone converted from 48 kHz: it must come out the right length, still at 1 kHz, with a click at 0.5 s still at 0.5 s. The last check matters because beat grids and cue points are stored as times.
- **The SOURCE panel showed a small stick as "768 MB".** The unit says "0.7 GB". The fix was tiny, but I only caught it because a test asserted what the unit shows.

And one test that had always passed failed on my machine, because I'd plugged a USB stick in. It was scanning the computer's real drives. Tests now only see the fake sticks they make for themselves.

## What's next

The full list is in the repo, in [TODO-cdj-3000.md](https://github.com/audiodestrukt/freedj-3000/blob/main/docs/TODO-cdj-3000.md). The big pieces:

- **For the touch builds:** a CDJ-3000 faceplate with an on-screen jog, and the jog's centre display. With a controller or a hardware deck those controls are physical, so they belong to the iPad and iPhone apps.
- **KEY SHIFT and key detection:** the panel is drawn but there's no key shifting engine behind it yet.
- **Library:** hot-cue colours from rekordbox, sorting, TRACK FILTER and the PLAYLIST bank.

The source is at [audiodestrukt/freedj-3000](https://github.com/audiodestrukt/freedj-3000), and the grid-key findings, with all the measurements, are in [cdj-grid-adjust.md](https://github.com/audiodestrukt/freedj-3000/blob/main/docs/design/cdj-grid-adjust.md).

*freedj-3000 and OpenDeck are independent projects, not affiliated with or endorsed by AlphaTheta or Pioneer DJ. CDJ-3000, XDJ-1000MK2 and rekordbox are their trademarks, named here to describe compatibility.*

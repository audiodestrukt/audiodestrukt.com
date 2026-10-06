---
title: "The board is the cassette"
date: 2026-10-05T12:00:00-07:00
tags: flexisette, cassette, flex pcb, esp32, tscircuit, build123d, hardware
image: images/2026-10-05_flexisette_assembly.png
---

# The board is the cassette

There's exactly one place on a compact cassette where you expect to see motion: the little window in the middle, where the reels turn and the tape crawls from one hub to the other. Everything else is a static shell. I kept coming back to that window. Put a screen there and animate it, and the most inert object in my parts bin becomes something that looks alive again.

So that's what flexisette is. It's the size and shape of a cassette, a 0.96″ OLED sits exactly where the tape window would be and loops a tape-winding animation, and an ESP32-S3 plays its own baked-in audio out a small speaker. It charges over USB-C and runs off a LiPo. It is not a prop that looks like a cassette; it's a self-contained little music object that happens to be shaped like one.

![The exploded stack: the cassette-face panel on top, the routed board under it, the printed spacer frame between them, and the head insert standing up through the middle](images/2026-10-05_flexisette_assembly.png)

The other reason it exists is a working method I wanted to prove out. Everything here regenerates from source — the circuit, the board placement, the enclosure parts, the fab outputs, even these renders are produced by code and data in one repo. I think of versions as *drops*: shipping a different one is editing data, not redrawing a design. Nothing in this post was placed by hand on a canvas.

## The outline is the only shape that matters

The board edge isn't styled to look cassette-ish. It *is* the cassette face, pulled from the same profile as the 3D-printed shell, down to the stepped notch along the bottom where a real deck's head and pinch roller would reach in. The two reel hubs are holes. The four corner screws are holes. The OLED's active area lands in the tape window. Once you accept that, the board stops being a rectangle you decorate and becomes a set of hard constraints you route around.

![The board edge (black) with the OLED cutout and its 21.7×10.9 mm active area dropped into the tape window, the four corner mounting holes, and the two reel openings as dashed keep-outs](images/2026-10-05_flexisette_board-outline.png)

That reframes placement. A normal board, you put parts down and then worry about the mechanical openings. Here the openings came first and the parts had to find room between them. The ESP32 module, the USB-C/charger/LDO power chain, the I²S amp, and four tactile switches all have to live in the margins around two big round holes in the middle of the board.

![Floorplan: everything packed into the margins around the two reel keep-outs — MCU block at left, power chain across the top, audio at right, switches along the bottom edge](images/2026-10-05_flexisette_floorplan.png)

The electronics themselves are deliberately boring, because boring is what gets assembled turnkey. ESP32-S3-WROOM-1 with native USB for the brain. SSD1306 OLED on I²C for the window. A MAX98357A I²S class-D amp into the speaker. USB-C into a TP4056 charger, a LiPo, and an ME6211 LDO for 3V3. Every part is JLCPCB/LCSC stocked. The board is generated module by module in tscircuit — React components for each subcircuit, composed into one design, placed deterministically, poured with ground, and finished in KiCad.

![The routed board in tscircuit: ESP32 (U1) and the four switches at left, the USB-C / charger / LDO chain across the top, the SSD1306 footprint filling the center, and the I²S amp feeding the speaker header at right](images/2026-10-05_flexisette_board.png)

## The window earns its keep

The whole conceit falls apart if the screen in the window is boring, so the firmware's first job — and honestly most of what runs today — is the tape animation. Two reels wind at 128×64, one paying out while the other takes up, with the tape path drawn between them. It's the one frame of this project that has to sell the illusion, and at OLED resolution the chunky hubs read exactly like the real thing through the shell's window.

![The 128×64 tape-winding animation: two hubs with wound tape and the tape path slung between them, drawn for the SSD1306](images/2026-10-05_flexisette_tape.png)

## The seam, where most of the risk lives

A board and the enclosure it lives in are really one design, and the place projects die is the seam between them — a connector that doesn't reach its slot, a screw that misses its boss, a display behind the wrong part of the window. Parameters lie about this; a `SHELL_W` constant won't stop you drawing a board 2 mm too wide. So the fit-check brings the actual routed board *into* the actual printed-part assembly, co-registers them on a shared datum, and renders them together. Alignment becomes a gate on where parts are allowed to go, not something you eyeball at the end.

![Fit-check: the routed board (green) co-registered inside the printed shell — top frame, spacer, and the head insert standing proud through the middle — on a shared datum so cutouts and holes have to line up](images/2026-10-05_flexisette_fit.png)

The printed parts aren't drawn from scratch either. They're carved parametrically out of a real vendor cassette shell (a Minecraft-cassette remix off Printables), so the frame, panel, and insert inherit the genuine cassette geometry instead of my guess at it.

## The speaker is where I had to be honest

I wanted bass. The cassette interior had other ideas. The only sealed volume I could carve is the head-insert bar — a 16×70×9 mm sliver — and it has to share even that with a slot I'm reserving for a future tape head. The driver, a PUI AS01808AO, lies flat against a broad face and fires out through a grille; everything behind it is the sealed back-volume.

![The carved speaker: grille slots and driver aperture on the sealed bar (left), and the hollowed chamber in cutaway (right)](images/2026-10-05_flexisette_speaker.png)

So I modeled it properly before believing anything — a Thiele-Small lumped acoustic circuit in ngspice, cross-checked against a closed-form solve (they agree to 0.00%). The verdict was unambiguous and not what I wanted. At the ~3.6 cm³ I can actually carve, with the driver's real 420 Hz resonance, the system knee lands around 874 Hz with a peaky Qtc near 2.1. A sealed box can only push that knee *up* from the driver's own Fs, never down. And it's excursion-limited well before it's power-limited: about 590 mW of clean output, roughly 79 dB at a meter.

![The sealed-box sim: SPL vs back-volume (top left), cone excursion against the 0.35 mm Xmax limit (top right), how Fc and Qtc fall as you add volume you don't have (bottom left), and the impedance hump (bottom right)](images/2026-10-05_flexisette_speaker-sim.png)

That's a midrange-presence driver, not a boombox — a clip player with some bite, which is the honest thing a cassette-sized sealed sliver can be. The sim's value wasn't a better number; it was killing the bass fantasy before I carved anything.

## Where it's going

The firmware is early, and the feature I actually want is the one that justifies the whole shape: drop the flexisette into a *real* cassette deck and have it play. An encoder reads the reels as the deck's transport winds them and syncs playback rate to the hub speed — normal on play, garbled on fast-forward, stopped on pause. A small tape head in the insert emits flux into the deck's own playback head, so the deck plays the flexisette's audio through its own electronics. It's the Bluetooth-cassette-adapter trick run backwards: emit instead of receive. That's what the reserved slot in the speaker bar is for.

None of that is built yet. But the board is fabbable, the shell fits it, the window animates, and the whole thing rebuilds from a `make`. The rest is firmware and one small magnetic part.

Source is on GitHub as [flexisette](https://github.com/audiodestrukt/flexisette).

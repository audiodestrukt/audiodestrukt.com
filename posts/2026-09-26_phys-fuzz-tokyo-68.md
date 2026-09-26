---
title: "Phys Fuzz 0.2: a second circuit, Tokyo '68"
date: 2026-09-26T10:00:00-07:00
tags: phys fuzz, plugins, circuit simulation, fuzz, ngspice
---

# Phys Fuzz 0.2: a second circuit, Tokyo '68

Phys Fuzz is the fuzz plugin where the knobs are component failures. It doesn't model the sound of a pedal, it solves the circuit. Every sample, the transistors get their junction voltages solved by Newton's method at four times the sample rate, and the knobs under the board (Battery, Age, Temperature) change the parts. Starve the battery and the sag pumps with your playing. Turn up Age and the junctions leak, the caps dry out, the bias drifts cold. You can automate all of it.

Until now there was one circuit in there: London '66, the two-transistor silicon fuzz everybody knows from the round box with the smile on it. 0.2.0 adds a second one, and a Circuit menu above the board to pick it.

## Tokyo '68

The new circuit is a Japanese two-stage fuzz from the late sixties, the one that got sold under a dozen brand names and is famous for sounding like a wasp in a tin can. It's a different animal from the London circuit even though it's also two silicon transistors.

Each stage biases itself with a resistor from collector back to base, and the second stage doesn't even get the full battery: its collector resistor hangs off a 100k in series with the supply, so the transistor idles at about one volt on the collector. That's the gate. Anything below a certain level just doesn't get through, and notes cut off with a snap instead of a fade.

The Fuzz knob is not a gain control. It's a 50k pot with the first stage's collector feeding the wiper and the second stage's collector feeding one end, with the output taken from the other end. So it pans between a one-stage fuzz and a two-stage fuzz, and it changes texture more than amount. On the pedal most people just leave it up. Then there's the part that makes it sound the way it does: a passive mid scoop, a 1000 pF cap bridged by 10k and 15k into 100 nF. Lows get through the resistors, highs get through the cap, the mids fall in the hole, and the whole thing comes out about 30 dB quieter than the London circuit. The plugin makes that gain back for you, but the shape stays.

![Tokyo '68 on the board](images/2026-09-26_phys-fuzz-tokyo-68_board.png)

## Same riff, both circuits

The same synthetic riff, through London '66 and then Tokyo '68, everything else at the defaults.

<audio controls preload="none" src="../../audio/phys-fuzz-riff-london-66.mp3"></audio>

<audio controls preload="none" src="../../audio/phys-fuzz-riff-tokyo-68.mp3"></audio>

## How it got in there

Every circuit in Phys Fuzz starts as an ngspice deck. I traced this one from a schematic, wrote the deck with every part as a parameter, and then wrote the same netlist for the realtime engine. The engine isn't a hand-written solver for this circuit. It's the general one that takes a netlist of resistors, capacitors, inductors, sources and transistors and derives the realtime solver itself. The transistor model is the same Gummel-Poon subset in both.

Then you compare. Bias point first: both collectors match ngspice to its printed precision, 3.595 V and 1.021 V. Then a five second riff through both at 192 kHz, every preset, with the DC stripped: the engine's output is within about 3% RMS of ngspice on every one, and the residual is ngspice's variable step size on the edges rather than anything I can hear. The London circuit's hand-built solver is at 6 to 12% on its own deck by the same measure, so the netlist engine is actually the more faithful of the two.

![ngspice (grey) against the realtime engine (red), a few cycles into the riff](images/2026-09-26_phys-fuzz-tokyo-68_ngspice.png)

It runs about twenty times realtime at 4x oversampling with Newton converging in 1.3 iterations a sample on average, and I swept every one of its 31 components to both ends of its range without a single solver failure.

## The same knobs

The point of doing it this way is that Battery, Age and Temperature don't need to know which circuit they're driving. Battery is the battery. Temperature scales the transistor model the way silicon actually drifts. Age leaks the junctions, fades the gain and drifts the bias cold. On this circuit "bias" means the 1M2 feedback resistor on the second stage, and the junction leak had to be given a gentler range, because a 30k leak across a megohm bias resistor doesn't age a stage, it kills it.

![Barn Find on Tokyo '68: scorched transistors, leak paths drawn in](images/2026-09-26_phys-fuzz-tokyo-68_barn-find.png)

The presets work on both circuits. Barn Find on Tokyo '68 is worth a listen: the second stage is barely alive to begin with, and the leaky junctions push it further.

## Switching without the click

Changing circuits mid-song works. The new circuit gets a warm start, its DC operating point re-solved, so there's no thump. The first version clicked anyway, for exactly eleven samples, and it took a while to see why. The two circuits put out very different levels, three volts versus a hundred millivolts, and each has its own output scale. I was applying that scale after the downsampling filter, so at the moment of the switch the filter's memory was still full of the old circuit's volts, now multiplied by the new circuit's thirty-times-bigger scale. Moving the multiply inside the oversampled loop fixed it. Both directions are clean now, so you can automate the Circuit parameter like anything else.

## Names

The menu says London '66 and Tokyo '68 rather than the pedal names, which belong to other people. The circuits are what they are. The names say where and when they came from.

## Get it

Phys Fuzz 0.2.0 is built for macOS (VST3 and AU, signed and notarized), Windows (VST3) and Linux (VST3): [releases](https://github.com/audiodestrukt/circuit-decimator/releases).

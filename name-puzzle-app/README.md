# Name puzzle app

Type a name, look at the board, and download a 3MF for a Bambu Lab P2S.

Short names stay at the same letter size as the printed FINN puzzle. Longer names are scaled down in the plane until the board is 247.5 mm wide, which leaves a few millimetres of bed on each side. The letters stay 11 mm thick, and each slot stays 0.40 mm larger than its letter. Counters such as O, R, A, and B stay in the board as islands.

The file is a closed mesh and a single-nozzle P2S project. Plate 1 is the board. Plate 2 is the letters. It does not replace the printer's extruder type or the filament start G-code.

## Run

From this directory:

```bash
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000. CadQuery and the other Python packages are listed in `requirements.txt`. Building a puzzle takes a minute or two; the page shows progress and keeps the form free.

A name can also be built without the page:

```bash
python3 puzzle.py ROB /tmp/rob-puzzle
```

## Print

Slots up. 0.20 mm layers, PLA. On the board, use 9 top shells and 9 bottom shells so the 3.5 mm floor is solid. Ironing off. Brim off. If one letter is tight, scale that letter to 99%, not the board.

Letters set in [Lilita One](fonts/OFL.txt) by Juan Montoreano.

# Name puzzle app

Type a name, look at the board, and download a 3MF for a Bambu Lab P2S.

The board is always turned 45° on plate 1. A short name stays at the same letter size as the printed FINN puzzle. A longer name is scaled down in the plane until the turned board still clears the 256 mm bed. That is what lets a name such as Johanne use a board longer than the bed is wide. The letters stay 11 mm thick, and each slot stays 0.40 mm larger than its letter. Counters such as O, R, A, and B stay in the board as islands.

The file is a closed mesh and a single-nozzle P2S project. Plate 1 is the board. The letters follow, at most four on a plate, printed with the show face up. That top face is ironed. Every plate is set to print by layer, because a height pause is unavailable when a plate prints by object. The file does not replace the printer's extruder type or the filament start G-code.

## Run

Use Python 3.11 or newer, in this folder, not the places-to-visit `backend/.venv`. That environment is Python 3.9, and CadQuery 2.8 will not install there. On a Mac:

```bash
brew install python@3.11
cd name-puzzle-app
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000. If the page is opened from the Python 3.9 backend environment, it stays up and says how to start this one instead of crashing on import.

Building a puzzle takes a minute or two. The page shows progress and keeps the form free.

A name can also be built without the page. Add `--magnets` for the 5×2 mm pockets:

```bash
python puzzle.py OLAV /tmp/olav-puzzle --magnets
```

## Magnets

The checkbox adds two pockets per letter, for 5 mm × 2 mm discs, and a matching pocket in the board floor under each one. The pocket is 5.4 mm across and 2.2 mm deep, so the magnet drops in and sits just below the plastic that closes over it. A letter that is too narrow for two pockets gets one, and the page says so.

The 3MF pauses the print before that cover. Every plate prints by layer, so the pause is active when the file opens:

- Board, plate 1: pause at 3.20 mm
- Each letter plate: pause at 2.80 mm

The letter pause is while the pocket is still open. The rest of the letter then prints over the magnets, so they stay buried instead of sticking to the nozzle. The file pins the layer height at 0.20 mm so those pauses land on the open pocket. Put every magnet in the same way up, on the letters and on the board, so the pairs pull together.

## Print

The 3MF already selects the P2S, 0.20 mm layers, 5 top shells, 5 bottom shells, 0.1 mm elephant foot compensation, and no brim. The show face is monotonic lines, then ironed. Ironing stays on the topmost surface, with rectilinear lines, 10% flow, 0.1 mm spacing, 15 mm/s, and a 0.2 mm inset so the edge stays sharp. Five shells are 1.0 mm of solid plastic on each face. The middle of the 3.5 mm floor stays infill. Board slots up. Letters show-face up. Every plate prints by layer. PLA. If one letter is tight, scale that letter to 99%, not the board. At most four letters share a plate.

Letters set in [Lilita One](fonts/OFL.txt) by Juan Montoreano.

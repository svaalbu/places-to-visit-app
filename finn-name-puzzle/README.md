# FINN name puzzle

A name puzzle for a Bambu Lab P2S, in the style of a painted wooden letter board. The board is one piece. Each slot is the outline of that letter, so the F only fits the F hole and an N only fits an N hole.

![FINN seated in the board](preview/finn_puzzle_seated.png)

![Yellow N lifted off its matching hole](preview/finn_puzzle_angle.png)

![Empty letter-shaped holes](preview/finn_puzzle_holes.png)

## Print this

The P2S build volume is 256 × 256 × 256 mm. The board is **236 × 96 × 16 mm**, so it fits on the bed with about 10 mm to spare. Center it if the slicer does not.

Use a **0.4 mm nozzle** and **PLA**. A matte or wood-tone PLA looks the most like the painted board in the photo. The printer has one nozzle, so print each color on its own plate. That avoids an AMS and the wasted filament from color changes.

| Piece | File | Suggested PLA | How many |
| --- | --- | --- | --- |
| Board | `stl/finn_board.stl` | Tan, beige, or wood | 1 |
| F | `stl/finn_letter_F.stl` | Red | 1 |
| I | `stl/finn_letter_I.stl` | Blue | 1 |
| N | `stl/finn_letter_N.stl` | Green | 1 |
| N | `stl/finn_letter_N.stl` | Yellow | 1 |

The two N pieces are the same shape. Print that file twice.

`finn_name_puzzle.3mf` is a Bambu Studio project for the **Bambu Lab P2S, 0.4 mm nozzle**, using the **0.20 mm Standard** process and five **PLA Basic** slots (tan, red, blue, green, yellow). Open that file. The pieces are already separate objects on one plate. Printing several colors in one job needs an AMS and spends a lot of filament on purges, so separate plates are the better default.

### On the bed

- **Board:** flat, slots facing up. No supports.
- **Letters:** flat. The broader flat face goes on the build plate. The softer top edge faces up. No supports and no brim.

### Bambu Studio settings

The 3MF already selects the P2S 0.4 mm nozzle and 0.20 mm Standard. If you start from the STL files instead, use Generic PLA and then:

- Layer height **0.20 mm** (0.16 mm if you want smoother sides on the letters)
- Walls **4**
- Infill **15% gyroid**
- Top and bottom shells **5**
- Ironing **on**, top surfaces only, so the letter faces look smooth
- Supports **off**
- Brim **off**
- Elephant foot compensation **0.10 mm**
- Seam position **back**

### Fit

Each hole is that letter, **0.40 mm** larger on every side. That is the gap a 0.4 mm nozzle needs so the piece still drops in. The walls follow the letter, including the open side of the F and the diagonal of the N. F will not go in the I or N holes. Either N fits either N hole. Each letter sits about **4.5 mm** above the board, so it can be pinched out.

The meshes are closed. Bambu Studio should not ask you to repair open edges.

If a piece feels tight, scale **that letter** to 99% in the slicer. Leave the board at 100%.

## Sizes

| Piece | Size (mm) |
| --- | --- |
| Board | 236.1 × 95.8 × 16.0 |
| F | 37.8 × 67.8 × 15.5 |
| I | 37.6 × 66.8 × 15.5 |
| N | 52.3 × 67.0 × 15.5 |

The slots are 11 mm deep. The letters are 15.5 mm thick.

![Top view](preview/finn_puzzle_top.png)

These pieces are large for a toddler toy. The smallest letter is still about 38 mm wide and 67 mm tall. Supervise play the way you would with any small child's toy.

## Regenerating the files

```bash
pip install -r requirements.txt
python3 generate.py
```

The letter shapes come from [Lilita One](https://fonts.google.com/specimen/Lilita+One) by Juan Montoreano, included under the SIL Open Font License (`fonts/OFL.txt`). The script only builds the name FINN. F, I, and N are solid strokes, which is what the slot fit is checked against.

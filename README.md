# Team 18 — FPGA Co-op Docking | External Display

ORBITAL / 18 — Python laptop viewer for the FPGA-controlled spaceship.

## Run on Windows

1. Install Python 3 (with Tcl/Tk, included by default).
2. Clone this repository or select Code > Download ZIP and extract it.
3. Open PowerShell in the extracted project folder.

```powershell
py -m pip install -r requirements.txt
py viewer.py
```

On macOS/Linux use `python3` instead of `py`. Install Tkinter using your Python distribution if missing. Test modes work without pySerial.

## Test without the board (stage A)

- **Test replay**: replays authored coordinate messages at 20 Hz, showing upward thrust, coasting, braking, horizontal movement, success, restart and failure. These are test snapshots only, not local physics.
- **Test constant**: repeatedly feeds `S,0320,0400,1,1\n` through the parser. The center must be (320,400), flame below the ship, state RUNNING.
- Test modes are explicitly labeled TEST DATA; they close the physical serial connection.
- **Disconnect** stops the test or serial connection.

## Test the actual board (stage B)

1. Power the FPGA normally. Use the existing JTAG cable for programming in Vivado.
2. Connect the board's **USB to Serial** socket to the laptop (not the 9-pin UART connector).
3. In Windows Device Manager > Ports (COM & LPT), find the COM port. Install the board-specific serial driver if needed; close any other serial terminal.
4. Ask the FPGA developer to transmit the constant message below 20 times per second. The guide lists USB_TXD0 = F6 and USB_RXD0 = C6; only TX is needed for this viewer. Confirm the actual board constraints before synthesis.
5. Click Refresh, choose the COM port, then Connect. The header must read LIVE FPGA, and valid frames should accumulate. Check the same (320,400) position and RUNNING state as in the local constant test.
6. Stop transmission while leaving the port open: after approximately 1 second the viewer should report STALE DATA and retain the last valid position.

## UART contract (proposed defaults, agree with FPGA developer)

- 9600 baud, 8 data bits, no parity, 1 stop bit, no flow control.
- 20 complete messages/second (one every 50 ms).
- ASCII `S,xxxx,yyyy,t,s` + LF (byte 0x0A), exactly 16 bytes including LF. No CR.
- `xxxx`: x = 0000–0639; `yyyy`: y = 0000–0479. Coordinates are ship center; origin top left, x right, y down.
- `t`: one hexadecimal digit; up=1, down=2, left=4, right=8. Bits can combine (up+right=9). Opposing thrusts must cancel on FPGA.
- `s`: 0 waiting, 1 running, 2 success, 3 failure.
- Example on wire: `S,0320,0400,1,1\n` where `\n` is one LF byte.
- The viewer rejects malformed fields, invalid ranges, overlong lines; buffers incomplete data and displays the newest valid message. It polls non-blocking at 25 ms intervals, and holds the last position between messages.

## Integrate live movement (stage C)

- Press board buttons: ship moves in the corresponding direction and flame appears opposite reported thrust.
- Release: verify continued movement if the FPGA reports inertia, with no thrust flame.
- Reverse thrust: verify braking in the FPGA-reported coordinates.
- Restart: confirm FPGA sends the new starting position and state.
- The viewer does not compute speed, acceleration, fuel, collisions, docking results or safety status. Success and failure are shown only when the FPGA reports them.
- Display-only docking port geometry: x=270–370, y=14–48; ship artwork is centered at incoming coordinates. Confirm this visual geometry with the FPGA developer before later docking/collision integration. No geometry is used for decisions.

## Automated protocol tests

```powershell
py -m unittest -v
```

The local tests cover valid messages, bounds, hexadecimal thrust, invalid fields, split packets, multiple messages, recovery after long garbage and game states. Physical FPGA integration must be verified with the board and its actual firmware.

## ORBITAL / 18 visual update

The redesigned viewer adds a flight HUD, coordinate readout, thrust direction indicators and a serial status panel. Geometry and UART protocol are unchanged; all mission decisions remain on the FPGA.

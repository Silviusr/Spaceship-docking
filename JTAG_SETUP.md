# JTAG-only setup — DLC9LP / ORBITAL 18

This is the primary connection method when the only available cable is the Xilinx Platform Cable USB (DLC9LP). No USB-UART cable, COM port or serial driver is needed. Vivado must remain connected to the programmed FPGA while playing.

## 1. FPGA developer (Vivado)

Open the existing game project, not a new standalone FPGA design.

1. Open IP Catalog, find Virtual Input/Output (VIO), and customize it:
   - Component name: orbital_vio
   - Input probes: 1
   - Output probes: 0
   - probe_in0 width: 25
   - Disable input activity detector if desired.
2. Generate Output Products. Add fpga/orbital_telemetry.v as a Design Source.
3. Instantiate the telemetry wrapper in the existing top-level module. Example (adapt names to your actual RTL):

```verilog
orbital_telemetry telemetry (
    .clk(clk),
    .ship_x(ship_x),
    .ship_y(ship_y),
    .thrust(thrust),
    .game_state(game_state)
);
```

The clock must be free-running and shared by the game state registers. Do not use a slow tick pulse as a clock. If game signals use different clock domains, synchronize them coherently first. Coordinates are unsigned ship-center pixels, not fixed-point velocities; convert them on the FPGA if needed. No new external XDC pin is needed for VIO. Keep all existing board constraints.

Snapshot layout: [24:15] x (0–639), [14:6] y (0–479), [5:2] thrust (up=1, down=2, left=4, right=8), [1:0] game state (0 waiting, 1 running, 2 success, 3 failure). Opposite thrusts cancel on the FPGA.

4. Re-run synthesis, implementation and generate bitstream. Keep the matching .ltx debug probes file (often debug_nets.ltx).
5. Power the board normally, connect DLC9LP to its JTAG header and PC USB, open Hardware Manager, Auto Connect, select the FPGA and Program Device. Select both the generated .bit and matching .ltx. Check that the VIO core and a 25-bit probe named orbital_snapshot (possibly a hierarchical name) are visible. If Vivado names the probe differently, inspect its name using the commands below and adjust the match in the bridge; do not pick an unrelated probe.
6. Do not close Hardware Manager or unplug the cable during play.

## 2. Windows viewer

Install Python 3 with Tcl/Tk. Download or clone this repository. Double-click run_jtag_windows.bat (or run py jtag_viewer.py from the project folder). No pip install is required for JTAG. Click **Listen JTAG**.

In the Vivado Tcl Console with Hardware Manager open and the programmed FPGA selected, run:

```tcl
source {C:/Users/YOUR_NAME/Downloads/Spaceship-docking-main/jtag_bridge.tcl}
orbital_start
```

Replace the path with your real extracted folder. Forward slashes or braces around the path are important.

The bridge polls VIO and sends newline-delimited position messages to Python on 127.0.0.1:18718. The TCP link is software-only, on the same computer; JTAG remains the only physical data cable. The viewer waits for valid frames, then renders the FPGA-reported state. There is no local physics or docking decision.

If 50 ms polling is too slow or Vivado becomes sluggish, try:

```tcl
orbital_stop
orbital_start 100
```

This requests 10 Hz. Actual refresh rate depends on Vivado, debug hub and programmer; 20 Hz is a target, not a measured guarantee.

To stop or reprogram: run orbital_stop in Tcl, then Disconnect in Python. When restarting, click Listen JTAG again before orbital_start.

## 3. Verify in stages

- Test replay and Test constant are still available without the board.
- Test the TCP link without FPGA: click Listen JTAG, then in a normal Tcl console run the following once. This is only a synthetic transport check; close the socket afterward. A real hardware test is still required.

```tcl
set c [socket 127.0.0.1 18718]
fconfigure $c -translation lf -buffering none -encoding ascii
puts $c "S,0320,0400,1,1"
# Keep socket open while observing the viewer, then:
close $c
```

- In FPGA firmware use a temporary known snapshot x=320, y=400, thrust=1, state=1 (packed HEX A06405). Confirm the VIO probe reports it and the viewer shows the same values. Remove temporary constants afterward.
- Connect the real game registers and verify button movement, coasting, braking, restart and success/failure. Stop updates and verify the viewer indicates stale data.
- If the VIO core is missing, confirm matching .bit/.ltx, free-running clock, debug hub clock and JTAG detection. Inspect available cores and probe names:

```tcl
get_hw_vios -of_objects [current_hw_device]
foreach v [get_hw_vios -of_objects [current_hw_device]] {
    foreach p [get_hw_probes -of_objects $v] {
        puts [get_property NAME $p]
    }
}
```

The UART-only viewer (viewer.py, run_windows.bat) remains available but is not needed for DLC9LP.

## References

AMD Vivado UG908, Description of hw_vio Tcl Commands and Reading VIO Inputs Using the VIO Cores View; UG835, refresh_hw_vio, get_hw_vios, get_hw_probes.

Hardware synthesis, actual DLC9LP communication and achievable rate must be verified on the team's physical board.

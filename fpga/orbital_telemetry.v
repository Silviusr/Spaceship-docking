// Add this module and a VIO IP named orbital_vio to the existing design.
// The game state signals must be synchronous to clk.
// This module only exports a snapshot; it does not implement game physics.
module orbital_telemetry (
    input wire clk,
    input wire [9:0] ship_x,
    input wire [8:0] ship_y,
    input wire [3:0] thrust,
    input wire [1:0] game_state
);
    (* keep = "true", mark_debug = "true" *) reg [24:0] orbital_snapshot;
    always @(posedge clk) begin
        orbital_snapshot <= {ship_x, ship_y, thrust, game_state};
    end
    orbital_vio u_orbital_vio (
        .clk(clk),
        .probe_in0(orbital_snapshot)
    );
endmodule

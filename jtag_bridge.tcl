# Source this file in Vivado Hardware Manager Tcl Console AFTER programming.
# Then run orbital_start. Stop with orbital_stop.
namespace eval orbital {
    variable sock ""
    variable timer ""
    variable vio ""
    variable probe ""
    variable interval 50
}

proc orbital_stop {} {
    variable ::orbital::timer
    variable ::orbital::sock
    if {$timer ne ""} { after cancel $timer; set timer "" }
    if {$sock ne ""} { catch {close $sock}; set sock "" }
    puts "ORBITAL bridge stopped."
}

proc orbital_frame {raw} {
    set raw [string trim $raw]
    if {![regexp {^(0[xX])?([0-9a-fA-F]+)$} $raw -> prefix digits]} {
        error "Invalid HEX VIO value: $raw"
    }
    if {[scan $digits %x word] != 1 || $word < 0 || $word > 0x1ffffff} {
        error "Snapshot is not 25 bits: $raw"
    }
    set x [expr {($word >> 15) & 0x3ff}]
    set y [expr {($word >> 6) & 0x1ff}]
    set thrust [expr {($word >> 2) & 0xf}]
    set state [expr {$word & 3}]
    if {$x > 639 || $y > 479} { return "" }
    return [format "S,%04d,%04d,%X,%d" $x $y $thrust $state]
}

proc orbital_tick {} {
    variable ::orbital::sock
    variable ::orbital::timer
    variable ::orbital::vio
    variable ::orbital::probe
    variable ::orbital::interval
    set timer ""
    if {$sock eq ""} { return }
    set started [clock milliseconds]
    if {[catch {
        refresh_hw_vio $vio
        set frame [orbital_frame [get_property INPUT_VALUE $probe]]
        if {$frame ne ""} {
            puts $sock $frame
            flush $sock
            if {[chan pending output $sock] > 4096} {
                error "Python is not consuming data"
            }
        }
    } message]} {
        puts stderr "ORBITAL bridge error: $message"
        orbital_stop
        return
    }
    set delay [expr {max(1, $interval - ([clock milliseconds] - $started))}]
    set timer [after $delay orbital_tick]
}

proc orbital_start {{period_ms 50}} {
    variable ::orbital::sock
    variable ::orbital::vio
    variable ::orbital::probe
    variable ::orbital::interval
    if {![string is integer -strict $period_ms] || $period_ms < 50} {
        error "period_ms must be an integer >= 50"
    }
    orbital_stop
    set device [current_hw_device]
    if {$device eq ""} { error "Open Hardware Manager and select the programmed FPGA first" }
    set matches {}
    foreach core [get_hw_vios -of_objects $device] {
        foreach p [get_hw_probes -of_objects $core] {
            if {[string match "*orbital_snapshot*" [get_property NAME $p]]} {
                lappend matches [list $core $p]
            }
        }
    }
    if {[llength $matches] != 1} {
        error "Expected exactly one orbital_snapshot VIO probe; check the .ltx file and probe names: $matches"
    }
    lassign [lindex $matches 0] vio probe
    set_property INPUT_VALUE_RADIX HEX $probe
    set interval $period_ms
    set sock [socket 127.0.0.1 18718]
    fconfigure $sock -blocking 0 -buffering none -translation lf -encoding ascii
    puts "ORBITAL bridge connected. Target period: $interval ms. Probe: $probe"
    orbital_tick
}
puts "ORBITAL bridge loaded. Run orbital_start (or orbital_start 100) to begin."

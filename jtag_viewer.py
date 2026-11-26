"""JTAG-only transport for ORBITAL. No UART cable or pySerial required."""
import socket
import tkinter as tk
from viewer import Viewer

HOST = "127.0.0.1"
PORT = 18718


class JtagReceiver:
    """Nonblocking localhost listener with a serial-like interface for Viewer."""
    def __init__(self, port=PORT):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client = None
        self.pending = b""
        try:
            self.server.bind((HOST, port))
            self.server.listen(1)
            self.server.setblocking(False)
        except BaseException:
            self.server.close()
            raise

    @property
    def in_waiting(self):
        if self.client is None:
            try:
                self.client, _ = self.server.accept()
                self.client.setblocking(False)
            except BlockingIOError:
                return 0
        if not self.pending:
            try:
                self.pending = self.client.recv(8192)
            except BlockingIOError:
                return 0
            if not self.pending:
                raise OSError("Vivado bridge closed; click Listen JTAG to reconnect.")
        return len(self.pending)

    def read(self, count):
        data, self.pending = self.pending[:count], self.pending[count:]
        return data

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None
        self.server.close()
        self.pending = b""


class JtagViewer(Viewer):
    def build_ui(self):
        super().build_ui()
        self.root.title("ORBITAL / 18 — JTAG + VIO")
        replacements = {
            "UART PORT": "JTAG LINK",
            "Refresh": "Reset port",
            "Connect": "Listen JTAG",
            "05  /  SERIAL LINK": "05  /  JTAG LINK",
            "9600 baud  /  8N1": "VIO / localhost TCP",
            "Expected stream: 20 Hz": "Target: up to 20 Hz",
        }
        def relabel(widget):
            if isinstance(widget, (tk.Label, tk.Button)):
                old = widget.cget("text")
                if old in replacements:
                    widget.configure(text=replacements[old])
            for child in widget.winfo_children():
                relabel(child)
        relabel(self.root)
        self.ports.configure(state="readonly")
        self.transport_note = "Click Listen JTAG, then run orbital_start in Vivado Tcl Console."
        self.status.set(self.transport_note)

    def refresh_ports(self):
        self.ports["values"] = (str(PORT),)
        self.port_name.set(str(PORT))

    def connect(self):
        self.reset_stream("idle", "Opening localhost listener...")
        try:
            self.port = JtagReceiver()
        except OSError as exc:
            self.transport_note = f"Cannot listen on port {PORT}: {exc}"
            return
        self.mode = "live"
        self.mode_label.set("JTAG / VIO")
        self.transport_note = f"JTAG / VIO | {HOST}:{PORT}"

    def disconnect(self):
        self.reset_stream("idle", "Disconnected. Click Listen JTAG to reconnect.")

    def tick(self):
        super().tick()
        if self.mode == "live" and self.last_received is None:
            self.status.set("Awaiting Vivado data. Source jtag_bridge.tcl and run orbital_start.")
        elif self.mode == "idle" and self.transport_note.startswith("Serial disconnected:"):
            self.transport_note = self.transport_note.replace("Serial disconnected:", "JTAG disconnected:", 1)
            self.status.set(self.transport_note)


if __name__ == "__main__":
    root = tk.Tk()
    JtagViewer(root)
    root.mainloop()

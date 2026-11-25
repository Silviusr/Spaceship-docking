"""Team 18 — FPGA co-op docking external display (Week 1)."""
import re
import time
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

WIDTH, HEIGHT = 640, 480
BAUD = 9600
REFRESH_MS = 25
STALE_SECONDS = 1.0
FRAME = re.compile(rb'S,([0-9]{4}),([0-9]{4}),([0-9A-Fa-f]),([0-3])')
STATES = ('WAITING', 'RUNNING', 'SUCCESS', 'FAILURE')


@dataclass(frozen=True)
class ShipState:
    x: int
    y: int
    thrust: int
    state: int


def parse_frame(line):
    """Parse one LF-delimited payload (without LF). Reject invalid fields."""
    match = FRAME.fullmatch(line)
    if match is None:
        return None
    x, y = int(match[1]), int(match[2])
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        return None
    return ShipState(x, y, int(match[3], 16), int(match[4]))


class FrameBuffer:
    """Bounded LF framer; a bad/oversized line cannot poison later frames."""
    def __init__(self):
        self.partial = bytearray()
        self.discard = False
        self.valid = 0
        self.invalid = 0

    def feed(self, data):
        newest = None
        for byte in data:
            if byte == 10:
                state = None if self.discard else parse_frame(bytes(self.partial))
                if state is None:
                    self.invalid += 1
                else:
                    self.valid += 1
                    newest = state
                self.partial.clear()
                self.discard = False
            elif not self.discard:
                if len(self.partial) == 15:
                    self.partial.clear()
                    self.discard = True
                else:
                    self.partial.append(byte)
        return newest


def sample_frame(x, y, thrust=0, state=1):
    return f'S,{x:04d},{y:04d},{thrust:X},{state}\n'.encode('ascii')


# Authored test snapshots only: no velocity, acceleration or game physics.
# The test replay emulates incoming UART frames, not FPGA logic.
DEMO_STAGES = [
    (0, [(220, 400, 0, 0)] * 20),
    (1, [(220, 400 - d, 1, 1) for d in (0, 1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66)]),
    (1, [(220, 323 - 11*i, 0, 1) for i in range(8)]),
    (1, [(220, y, 2, 1) for y in (235, 226, 218, 211, 205, 200, 196, 193, 191, 190)]),
    (1, [(x, 190, 8, 1) for x in range(220, 321, 5)]),
    (1, [(320, y, 1, 1) for y in range(190, 70, -4)]),
    (2, [(320, 70, 0, 2)] * 30),
    (0, [(220, 400, 0, 0)] * 15),
    (1, [(x, 400, 4, 1) for x in range(220, 0, -8)]),
    (3, [(0, 400, 0, 3)] * 30),
]
DEMO_FRAMES = [sample_frame(*snapshot) for _, stage in DEMO_STAGES for snapshot in stage]


class Viewer:
    def __init__(self, root):
        self.root = root
        root.title('Team 18 | FPGA Co-op Docking')
        root.configure(bg='#101927')
        root.resizable(False, False)
        self.port = None
        self.mode = 'idle'
        self.buffer = FrameBuffer()
        self.last_frame = None
        self.last_received = None
        self.mode_started = time.monotonic()
        self.demo_index = 0
        self.next_demo = 0
        self.transport_note = 'Select a COM port or start test data.'
        self.status = tk.StringVar(value=self.transport_note)
        self.port_name = tk.StringVar()
        self.mode_label = tk.StringVar(value='OFFLINE')
        self.state_label = tk.StringVar(value='NO DATA')
        self.position_label = tk.StringVar(value='X ----   Y ----')
        self.count_label = tk.StringVar(value='Valid 0  |  Rejected 0')
        self.build_ui()
        self.refresh_ports()
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.tick()

    def build_ui(self):
        import random
        bg, panel, line, ink, muted, cyan = '#080e19', '#101c2b', '#23384b', '#e4f0fa', '#8399af', '#64e8e4'
        self.root.configure(bg=bg)
        self.root.title('ORBITAL / Team 18 Docking Control')
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=panel, background=panel, foreground=ink, arrowcolor=cyan, bordercolor=line, padding=6)
        outer = tk.Frame(self.root, bg=bg, padx=20, pady=15)
        outer.pack(fill='both')
        def label(parent, text='', size=10, color=muted, bold=False, background=bg, **kw):
            return tk.Label(parent, text=text, font=('Arial', size, 'bold' if bold else 'normal'), fg=color, bg=background, **kw)
        def button(parent, title, action, primary=False):
            return tk.Button(parent, text=title, command=action, bg=cyan if primary else panel, fg=bg if primary else ink, activebackground='#b2fffa' if primary else '#29435b', activeforeground=bg if primary else ink, relief='flat', borderwidth=0, highlightthickness=0, padx=11, pady=7, font=('Arial', 10, 'bold'), cursor='hand2')
        top = tk.Frame(outer, bg=bg)
        top.pack(fill='x')
        brand = tk.Frame(top, bg=bg); brand.pack(side='left')
        label(brand, 'O R B I T A L  /  1 8', 21, ink, True).pack(anchor='w')
        label(brand, 'COOPERATIVE DOCKING  /  EXTERNAL DISPLAY', 9, muted, True).pack(anchor='w')
        badge = tk.Frame(top, bg=panel, padx=13, pady=9); badge.pack(side='right')
        label(badge, '●  DATA SOURCE', 9, muted, True, panel).pack(anchor='w')
        label(badge, size=13, color=cyan, bold=True, background=panel, textvariable=self.mode_label).pack(anchor='w')
        toolbar = tk.Frame(outer, bg=bg); toolbar.pack(fill='x', pady=(13,12))
        label(toolbar, 'UART PORT', 9, muted, True).pack(side='left', padx=(0,8))
        self.ports = ttk.Combobox(toolbar, textvariable=self.port_name, width=17); self.ports.pack(side='left')
        for title, action, primary in [('Refresh',self.refresh_ports,False),('Connect',self.connect,True),('Disconnect',self.disconnect,False)]:
            button(toolbar,title,action,primary).pack(side='left',padx=(5,0))
        button(toolbar,'Test constant',self.start_constant).pack(side='right')
        button(toolbar,'Test replay',self.start_demo).pack(side='right',padx=5)
        body = tk.Frame(outer,bg=bg); body.pack(fill='x')
        field = tk.Frame(body,bg=panel,highlightbackground=line,highlightthickness=1); field.pack(side='left')
        fieldtop=tk.Frame(field,bg=panel,padx=10,pady=8); fieldtop.pack(fill='x')
        label(fieldtop,'01  /  FLIGHT VIEW',10,ink,True,panel).pack(side='left')
        label(fieldtop,'640 × 480  ·  FPGA COORDINATES',9,muted,False,panel).pack(side='right')
        self.canvas=tk.Canvas(field,width=WIDTH,height=HEIGHT,bg='#060d19',highlightthickness=0); self.canvas.pack()
        c=self.canvas
        for x in range(0,WIDTH,40): c.create_line(x,0,x,HEIGHT,fill='#122235')
        for y in range(0,HEIGHT,40): c.create_line(0,y,WIDTH,y,fill='#122235')
        rng=random.Random(18)
        for _ in range(120):
            x,y=rng.randrange(6,634),rng.randrange(6,474)
            r=rng.choice((0.5,0.7,1.1)); c.create_oval(x-r,y-r,x+r,y+r,fill=rng.choice(('#24415a','#466078','#6a8397')),outline='')
        c.create_rectangle(1,1,638,478,outline='#41677e',width=2)
        for x,y,sx,sy in ((5,5,1,1),(635,5,-1,1),(5,475,1,-1),(635,475,-1,-1)):
            c.create_line(x,y+sy*14,x,y,x+sx*14,y,fill=cyan,width=2)
        c.create_line(320,49,320,479,fill='#397883',dash=(5,9))
        # Visual guides only; not used in docking decisions.
        for x in (295,345): c.create_line(x,49,x,479,fill='#17383e',dash=(3,9))
        for y in (80,160,240,320,400):
            c.create_line(311,y,329,y,fill='#3b6878'); c.create_text(337,y,text=f'{y:03}',anchor='w',fill='#537a8e',font=('Courier',8))
        c.create_rectangle(270,14,370,48,fill='#1d3547',outline=cyan,width=2)
        for x in (278,286,354,362): c.create_rectangle(x,20,x+4,42,fill='#547386',outline='')
        c.create_rectangle(295,35,345,48,fill='#061a24',outline=cyan,width=2)
        c.create_text(320,25,text='DOCK / 01',fill=ink,font=('Arial',9,'bold'))
        c.create_line(263,48,263,58,282,58,fill=cyan); c.create_line(377,48,377,58,358,58,fill=cyan)
        c.create_text(12,14,text='SECTOR A',anchor='nw',fill='#728da4',font=('Courier',9,'bold'))
        c.create_text(12,29,text='DISPLAY ONLY',anchor='nw',fill='#4c687e',font=('Courier',8))
        self.flames={bit:c.create_polygon(0,0,0,0,0,0,fill='#e6a04a',outline='#ffcf80',state='hidden') for bit in (1,2,4,8)}
        self.ship=c.create_polygon(0,0,0,0,0,0,fill='#d5e7f1',outline=cyan,width=2,state='hidden')
        self.cockpit=c.create_oval(0,0,0,0,fill='#24838e',outline='#a8fff8',state='hidden')
        self.banner_bg=c.create_rectangle(135,200,505,280,fill='#101c2b',outline='#54788b',width=2,state='hidden')
        self.banner=c.create_text(320,240,text='',font=('Arial',20,'bold'),fill=ink,state='hidden')
        self.watermark=c.create_text(627,466,anchor='se',text='',fill='#ffc87a',font=('Arial',9,'bold'))
        side=tk.Frame(body,bg=bg,width=220); side.pack(side='left',fill='y',padx=(12,0)); side.pack_propagate(False)
        def section(title):
            box=tk.Frame(side,bg=panel,padx=14,pady=12,highlightbackground=line,highlightthickness=1); box.pack(fill='x',pady=(0,8))
            label(box,title,9,muted,True,panel).pack(anchor='w'); return box
        status=section('02  /  MISSION STATE')
        self.state_widget=label(status,size=17,color=muted,bold=True,background=panel,textvariable=self.state_label); self.state_widget.pack(anchor='w',pady=(7,0))
        coords=section('03  /  SHIP POSITION')
        self.x_label=tk.StringVar(value='----'); self.y_label=tk.StringVar(value='----')
        for axis,var in [('X',self.x_label),('Y',self.y_label)]:
            r=tk.Frame(coords,bg=panel); r.pack(fill='x',pady=(4,0))
            label(r,axis,12,muted,True,panel).pack(side='left')
            tk.Label(r,textvariable=var,font=('Courier',24,'bold'),fg=ink,bg=panel).pack(side='right')
        thrust=section('04  /  THRUST VECTOR')
        arrows=tk.Frame(thrust,bg=panel); arrows.pack(pady=(8,0))
        self.thrust_widgets={}
        for bit,txt,row,col in [(1,'↑',0,1),(4,'←',1,0),(2,'↓',1,1),(8,'→',1,2)]:
            w=tk.Label(arrows,text=txt,width=3,font=('Arial',19,'bold'),fg='#648097',bg='#17283a',pady=4); w.grid(row=row,column=col,padx=2,pady=2); self.thrust_widgets[bit]=w
        stream=section('05  /  SERIAL LINK')
        label(stream,'9600 baud  /  8N1',11,ink,True,panel).pack(anchor='w',pady=(5,0))
        label(stream,'Expected stream: 20 Hz',9,muted,False,panel).pack(anchor='w',pady=(4,0))
        label(stream,size=9,background=panel,textvariable=self.count_label).pack(anchor='w',pady=(6,0))
        footer=tk.Frame(outer,bg=panel,padx=12,pady=8); footer.pack(fill='x',pady=(11,0))
        self.status_widget=label(footer,size=10,background=panel,textvariable=self.status,anchor='w',wraplength=820,justify='left'); self.status_widget.pack(fill='x')
        label(outer,'TEAM 18   /   LOGIC CIRCUIT DESIGN                                             FPGA IS THE SOURCE OF TRUTH',8,'#627a90',True).pack(fill='x',pady=(8,0))

    def refresh_ports(self):
        if list_ports is None:
            self.ports['values'] = ()
            return
        values = [p.device for p in list_ports.comports()]
        self.ports['values'] = values
        if values and not self.port_name.get():
            self.port_name.set(values[0])

    def stop_port(self):
        if self.port is not None:
            try:
                self.port.close()
            except (OSError, ValueError):
                pass
            self.port = None

    def reset_stream(self, mode, note):
        self.stop_port()
        self.mode = mode
        self.buffer = FrameBuffer()
        self.last_frame = None
        self.last_received = None
        self.mode_started = time.monotonic()
        self.transport_note = note
        self.mode_label.set({'idle':'OFFLINE', 'live':'LIVE FPGA', 'demo':'TEST DATA', 'constant':'TEST DATA'}[mode])
        self.state_label.set('NO DATA')
        self.state_widget.config(fg='#92a7bd')
        self.position_label.set('X ----   Y ----')
        self.x_label.set('----'); self.y_label.set('----')
        for w in self.thrust_widgets.values(): w.config(bg='#17283a', fg='#648097')
        self.canvas.itemconfigure(self.watermark, text='TEST DATA — NOT FPGA' if mode in ('demo','constant') else '')
        for item in [self.ship, self.cockpit, self.banner, self.banner_bg, *self.flames.values()]:
            self.canvas.itemconfigure(item, state='hidden')

    def connect(self):
        name = self.port_name.get().strip()
        self.reset_stream('idle', 'Connecting...')
        if serial is None:
            self.transport_note = 'pySerial missing: install with python -m pip install pyserial.'
            return
        if not name:
            self.transport_note = 'Select or enter a serial port first.'
            return
        try:
            self.port = serial.Serial(name, BAUD, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0, xonxoff=False, rtscts=False, dsrdtr=False)
        except (OSError, ValueError) as exc:
            self.transport_note = f'Connection failed: {exc}'
            return
        self.mode = 'live'
        self.mode_started = time.monotonic()
        self.mode_label.set('LIVE FPGA')
        self.transport_note = f'{name} | 9600 baud | 8N1'

    def disconnect(self):
        self.reset_stream('idle', 'Disconnected. Select a port or start test data.')

    def start_demo(self):
        self.reset_stream('demo', 'Replay of authored example messages at 20 Hz.')
        self.demo_index = 0
        self.next_demo = time.monotonic()

    def start_constant(self):
        self.reset_stream('constant', 'Constant sample message: S,0320,0400,1,1')
        self.next_demo = time.monotonic()

    def ingest(self, data, now):
        newest = self.buffer.feed(data)
        if newest is not None:
            self.last_frame = newest
            self.last_received = now
            self.draw(newest)

    def tick(self):
        now = time.monotonic()
        if self.mode == 'live' and self.port is not None:
            try:
                n = min(self.port.in_waiting, 8192)
                if n:
                    self.ingest(self.port.read(n), now)
            except (OSError, ValueError) as exc:
                self.stop_port()
                self.mode = 'idle'
                self.mode_label.set('OFFLINE')
                self.transport_note = f'Serial disconnected: {exc}'
                # Freeze the last known position and mark it as disconnected.
                self.state_label.set('DISCONNECTED')
                self.state_widget.config(fg='#ffc87a')
        elif self.mode in ('demo','constant') and now >= self.next_demo:
            frame = DEMO_FRAMES[self.demo_index] if self.mode == 'demo' else sample_frame(320,400,1,1)
            self.demo_index = (self.demo_index + 1) % len(DEMO_FRAMES)
            self.ingest(frame, now)
            self.next_demo += 0.05
            if self.next_demo < now:
                self.next_demo = now + 0.05
        if self.mode != 'idle':
            since = now - (self.last_received if self.last_received is not None else self.mode_started)
            if since >= STALE_SECONDS:
                self.status.set('STALE DATA — no valid update for 1 second; last position retained.')
                self.status_widget.config(fg='#ffc87a')
            else:
                self.status.set(self.transport_note if self.last_received is not None else 'Waiting for first valid message...')
                self.status_widget.config(fg='#92a7bd')
        else:
            self.status.set(self.transport_note)
            self.status_widget.config(fg='#92a7bd')
        self.count_label.set(f'Valid {self.buffer.valid}  |  Rejected {self.buffer.invalid}')
        self.root.after(REFRESH_MS, self.tick)

    def draw(self, frame):
        x, y = frame.x, frame.y
        c = self.canvas
        c.coords(self.ship, x,y-21, x+7,y-5, x+15,y+4, x+17,y+17, x+5,y+12, x,y+17, x-5,y+12, x-17,y+17, x-15,y+4, x-7,y-5)
        c.coords(self.cockpit, x-4,y-9, x+4,y+5)
        c.itemconfigure(self.ship, state='normal')
        c.itemconfigure(self.cockpit, state='normal')
        # Flames are opposite the reported thrust direction; no motion math.
        flame_points = {1:(x-5,y+10,x+5,y+10,x,y+26), 2:(x-5,y-10,x+5,y-10,x,y-27), 4:(x+9,y-4,x+9,y+6,x+25,y+1), 8:(x-9,y-4,x-9,y+6,x-25,y+1)}
        for bit, item in self.flames.items():
            c.coords(item, *flame_points[bit])
            c.itemconfigure(item, state='normal' if frame.thrust & bit else 'hidden')
        colors = ('#92a7bd', '#70d7e6', '#75e4ae', '#ff9393')
        self.state_label.set(STATES[frame.state])
        self.state_widget.config(fg=colors[frame.state])
        self.position_label.set(f'X {x:04d}   Y {y:04d}')
        self.x_label.set(f'{x:04d}'); self.y_label.set(f'{y:04d}')
        for bit,w in self.thrust_widgets.items():
            active=bool(frame.thrust & bit)
            w.config(bg='#64e8e4' if active else '#17283a', fg='#080e19' if active else '#648097')
        result = {2:'DOCKING SUCCESS', 3:'DOCKING FAILED'}.get(frame.state)
        c.itemconfigure(self.banner_bg, state='normal' if result else 'hidden')
        c.itemconfigure(self.banner, text=result or '', fill=colors[frame.state], state='normal' if result else 'hidden')

    def close(self):
        self.stop_port()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    Viewer(root)
    root.mainloop()

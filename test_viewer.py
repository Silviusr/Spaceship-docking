import unittest
from viewer import FrameBuffer, ShipState, parse_frame, sample_frame

class ProtocolTests(unittest.TestCase):
    def test_example(self):
        self.assertEqual(parse_frame(b'S,0320,0400,1,1'), ShipState(320,400,1,1))
        self.assertEqual(len(sample_frame(320,400,1,1)), 16)
    def test_boundaries_and_hex(self):
        self.assertEqual(parse_frame(b'S,0639,0479,A,3'), ShipState(639,479,10,3))
        self.assertEqual(parse_frame(b'S,0000,0000,f,0'), ShipState(0,0,15,0))
    def test_bad(self):
        for line in (b'X,0320,0400,1,1', b'S,0640,0400,1,1', b'S,0320,0480,1,1', b'S,0320,0400,G,1', b'S,0320,0400,1,4', b'S,320,0400,1,1', b'S,0320,0400,1,1,0', b'S,0320,0400,1,1\r', b'S,0x20,0400,1,1'):
            self.assertIsNone(parse_frame(line), line)
    def test_fragmented(self):
        buf = FrameBuffer()
        self.assertIsNone(buf.feed(b'S,0320,'))
        self.assertIsNone(buf.feed(b'0400,1,1'))
        self.assertEqual(buf.feed(b'\n'), ShipState(320,400,1,1))
    def test_latest(self):
        buf = FrameBuffer()
        self.assertEqual(buf.feed(sample_frame(10,20)+b'bad\n'+sample_frame(30,40,8,2)+b'bad\n'), ShipState(30,40,8,2))
        self.assertEqual((buf.valid,buf.invalid),(2,2))
    def test_recover_after_long_line(self):
        buf = FrameBuffer()
        self.assertIsNone(buf.feed(b'x'*10000))
        self.assertEqual(len(buf.partial), 0)
        self.assertEqual(buf.feed(b'\n'+sample_frame(320,400)), ShipState(320,400,0,1))
        self.assertEqual(buf.invalid,1)
    def test_all_states(self):
        for state in range(4):
            self.assertEqual(parse_frame(sample_frame(0,0,0,state)[:-1]).state,state)

if __name__ == '__main__':
    unittest.main()

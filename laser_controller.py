#!/usr/bin/python3
import time
import serial
import sys

def unscramble(data, magic=0x88):
    rlt = []
    for i in data:
        a = (i + 0xFF) & 0xFF
        b = a ^ magic
        rlt.append((b & 0x7E) | ((b >> 7) & 0x01) | ((b << 7) & 0x80))
    return rlt

def scramble(data, magic=0x88):
    rlt = []
    for i in data:
        a = (i & 0x7E) | ((i >> 7) & 0x01) | ((i << 7) & 0x80)
        b = a ^ magic
        rlt.append((b + 1) & 0xFF)
    return rlt

def reset_serial(s):
    s.setDTR(False)
    s.setRTS(False)
    time.sleep(0.1)
    
def init_serial(s):
    s.setDTR(False)
    s.setRTS(True)
    time.sleep(0.005)
    s.setDTR(True)
    s.setRTS(False)

def main():
    s = serial.Serial()
    s.port = "/dev/ttyUSB0"
    s.baudrate = 38400
    s.parity = serial.PARITY_NONE
    s.stopbits = serial.STOPBITS_ONE
    s.open()

    reset_serial(s)

    init_serial(s)

    with open(sys.argv[1], "rb") as f:
        s.write(f.read())
    #  s.write(scramble([0xeB]))
    print("Connected")
    return
    while True:
        data = s.read()
        print([f"0x{i:02x}" for i in unscramble(data)])
    return

if __name__ == "__main__":
    main()

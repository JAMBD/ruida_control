#!/usr/bin/python3.7
import sys
import dataclasses
from dataclasses import dataclass
from matplotlib import pyplot as plt
import matplotlib as mpl
from typing import List, Tuple, Dict, Optional

@dataclass
class CmdCode:
    code: List[int]
    length: int

    def __init__(self, code):
        if isinstance(code, List):
            self.code = code
            self.length = len(code)
        else:
            self.code = [code]
            self.length = 1
    
    @classmethod
    def parse(cls, data):
        return cls(code=data[0])

    def pack(self):
        return self.code

@dataclass
class CmdMsg:
    cmd: CmdCode
        
    @classmethod
    def from_values(cls, **kargs):
        args = []
        for i in dataclasses.fields(cls):
            if hasattr(cls, i.name):
                type_or_attr = getattr(cls, i.name)
            else:
                type_or_attr = i.type
            
            if hasattr(cls, i.name):
                args.append(type_or_attr)
            else:
                if i.name in kargs:
                    args.append(type_or_attr.from_value(kargs[i.name]))
        return cls(*args)
    
    @classmethod
    def get_length(cls):
        total_length = 0
        for i in dataclasses.fields(cls):
            total_length += i.type.length
        return total_length

    @classmethod
    def parse(cls, data):
        args = []
        parsed_length = 0
        for i in dataclasses.fields(cls):
            if hasattr(cls, i.name):
                type_or_attr = getattr(cls, i.name)
            else:
                type_or_attr = i.type
            arg_length = type_or_attr.length
            arg_data = data[parsed_length: parsed_length + arg_length]
            parsed_length += arg_length

            if hasattr(cls, i.name):
                args.append(type_or_attr)
            else:
                args.append(type_or_attr.parse(arg_data))
        return cls(*args)

    def update(self, laser_sim):
        pass

    def pack(self):
        rlt = []
        for i in dataclasses.fields(self):
            if hasattr(self, i.name):
                rlt += getattr(self, i.name).pack()
        return rlt

@dataclass
class Value:
    value: int
    length: int
    signed: bool

    @classmethod
    def parse(cls, data):
        assert len(data) == cls.length
        value = 0
        for i in data:
            value = (value << 7) | i
        if cls.signed:
            if value > (1 << (cls.length * 7 - 1)):
                value -= (1 << (cls.length * 7))
        return cls(value=value, length=cls.length, signed=cls.signed)

    def pack(self):
        v = self.value
        if v < 0:
            v = v + (1 << (self.length * 7))
        data = []
        for i in range(self.length):
            data.append(v & 0x7F)
            v = v >> 7
        data.reverse()
        return data

    @classmethod
    def from_value(cls, value):
        return cls(length=cls.length, signed=cls.signed, value=value)
        

@dataclass
class AbsValue(Value):
    length = 5
    signed = False
    
@dataclass
class RelValue(Value):
    length = 2
    signed = True

@dataclass
class MilliSeconds(Value):
    length = 5
    signed = False

@dataclass
class Unknown(Value):
    length = 1
    signed = False

@dataclass
class Unknown2(Value):
    length = 2
    signed = False
    
@dataclass
class Device(Value):
    length = 1
    signed = False

@dataclass
class Layer(Value):
    length = 1
    signed = False
    
@dataclass
class Power(Value):
    length=2
    signed=False

@dataclass
class Speed(Value):
    length=5
    signed=False
    
@dataclass
class Color(Value):
    length = 5
    signed = False

    @property
    def red(self):
        return self.value & 0xFF

    @property
    def green(self):
        return (self.value >> 8) & 0xFF

    @property
    def blue(self):
        return (self.value >> 16) & 0xFF


@dataclass
class MoveAbs(CmdMsg):
    cmd=CmdCode(0x88)
    x: AbsValue
    y: AbsValue
    def update(self, laser_sim):
        laser_sim.move(self.x.value, self.y.value)

@dataclass
class MoveRel(CmdMsg):
    cmd=CmdCode(0x89)
    dx: RelValue
    dy: RelValue
    def update(self, laser_sim):
        laser_sim.move(self.dx.value, self.dy.value, relative=True)

@dataclass
class MoveHorz(CmdMsg):
    cmd=CmdCode(0x8A)
    distance: RelValue
    def update(self, laser_sim):
        laser_sim.move(self.distance.value, 0, relative=True)

@dataclass
class MoveVert(CmdMsg):
    cmd=CmdCode(0x8B)
    distance: RelValue
    def update(self, laser_sim):
        laser_sim.move(0, self.distance.value, relative=True)

@dataclass
class CutAbs(CmdMsg):
    cmd=CmdCode(0xA8)
    x: AbsValue
    y: AbsValue
    def update(self, laser_sim):
        laser_sim.move(self.x.value, self.y.value, cut=True)

@dataclass
class CutRel(CmdMsg):
    cmd=CmdCode(0xA9)
    dx: RelValue
    dy: RelValue
    def update(self, laser_sim):
        laser_sim.move(self.dx.value, self.dy.value, relative=True, cut=True)

@dataclass
class CutHorz(CmdMsg):
    cmd=CmdCode(0xAA)
    distance: RelValue
    def update(self, laser_sim):
        laser_sim.move(self.distance.value, 0, cut=True, relative=True)

@dataclass
class CutVert(CmdMsg):
    cmd=CmdCode(0xAB)
    distance: RelValue
    def update(self, laser_sim):
        laser_sim.move(0, self.distance.value, cut=True, relative=True)

@dataclass
class Feedrate(CmdMsg):
    cmd=CmdCode([0xe7, 0x06])
    x: AbsValue
    y: AbsValue

@dataclass
class LayerColor(CmdMsg):
    cmd=CmdCode([0xCA, 0x06])
    layer: Layer
    color: Color
    def update(self, laser_sim):
        laser_sim.set_layer_property(self.layer.value, color=(
                self.color.red/255.0,
                self.color.green/255.0,
                self.color.blue/255.0))
@dataclass
class LayerSpeed(CmdMsg):
    cmd=CmdCode([0xC9, 0x04])
    layer: Layer
    speed: Speed
    def update(self, laser_sim):
        laser_sim.set_layer_property(self.layer.value,
                                     speed=self.speed.value)

@dataclass
class LayerCA41(CmdMsg):
    cmd=CmdCode([0xCA, 0x41])
    layer: Layer
    u0: Unknown
        
@dataclass
class LayerLaser1TopLeft(CmdMsg):
    cmd=CmdCode([0xe7, 0x52])
    layer: Layer
    x: AbsValue
    y: AbsValue
    def update(self, laser_sim):
        laser_sim.set_layer_property(self.layer.value,
                                     x_min=self.x.value,
                                     y_min=self.y.value)  

@dataclass
class LayerLaser1BottomRight(CmdMsg):
    cmd=CmdCode([0xe7, 0x53])
    layer: Layer
    x: AbsValue
    y: AbsValue
    def update(self, laser_sim):
        laser_sim.set_layer_property(self.layer.value,
                                     x_max=self.x.value,
                                     y_max=self.y.value)
        
@dataclass
class LayerLaser2TopLeft(CmdMsg):
    cmd=CmdCode([0xe7, 0x61])
    layer: Layer
    x: AbsValue
    y: AbsValue

@dataclass
class LayerLaser2BottomRight(CmdMsg):
    cmd=CmdCode([0xe7, 0x62])
    layer: Layer
    x: AbsValue
    y: AbsValue
        
@dataclass
class LayerLaser1MaxPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x32])
    layer: Layer
    power: Power
    def update(self, laser_sim):
        laser_sim.set_layer_property(self.layer.value,
                                     max_power=self.power.value)
        
@dataclass
class LayerLaser1MinPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x31])
    layer: Layer
    power: Power
    def update(self, laser_sim):
        laser_sim.set_layer_property(self.layer.value,
                                     min_power=self.power.value)
@dataclass
class LayerLaser2MaxPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x42])
    layer: Layer
    power: Power

@dataclass
class LayerLaser2MinPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x41])
    layer: Layer
    power: Power

@dataclass
class CutPower1(CmdMsg):
    cmd=CmdCode([0xC6, 0x50])
    power: Power

@dataclass
class CutPower2(CmdMsg):
    cmd=CmdCode([0xC6, 0x51])
    power: Power

@dataclass
class Laser1MinPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x01])
    power: Power

@dataclass
class Laser1MaxPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x02])
    power: Power

@dataclass
class Laser2MinPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x21])
    power: Power

@dataclass
class Laser2MaxPower(CmdMsg):
    cmd=CmdCode([0xC6, 0x22])
    power: Power

@dataclass
class CutOpenDelay(CmdMsg):
    cmd=CmdCode([0xC6, 0x12])
    ms: MilliSeconds

@dataclass
class CutCloseDelay(CmdMsg):
    cmd=CmdCode([0xC6, 0x13])
    ms: MilliSeconds

@dataclass
class CutSpeed(CmdMsg):
    cmd=CmdCode([0xC9, 0x02])
    speed: Speed
        
@dataclass
class ChangeLayer(CmdMsg):
    cmd=CmdCode([0xCA, 0x02])
    layer: Layer
    def update(self, laser_sim):
        laser_sim.current_layer = self.layer.value

@dataclass
class EnableDevice(CmdMsg):
    cmd=CmdCode([0xCA, 0x01])
    device: Device

@dataclass
class CA03(CmdMsg):
    cmd=CmdCode([0xCA, 0x03])
    unknown: Unknown

@dataclass
class CA10(CmdMsg):
    cmd=CmdCode([0xCA, 0x10])
    unknown: Unknown

@dataclass
class UploadFollows(CmdMsg):
    cmd=CmdCode([0xD8, 0x12])

@dataclass
class Start2(CmdMsg):
    cmd=CmdCode([0xF1, 0x02, 0x00])
    
@dataclass
class Laser1TopLeft(CmdMsg):
    cmd=CmdCode([0xE7, 0x03])
    x: AbsValue
    y: AbsValue
    
@dataclass
class Laser1BottomRight(CmdMsg):
    cmd=CmdCode([0xE7, 0x07])
    x: AbsValue
    y: AbsValue

@dataclass
class Laser2TopLeft(CmdMsg):
    cmd=CmdCode([0xE7, 0x50])
    x: AbsValue
    y: AbsValue
    
@dataclass
class Laser2BottomRight(CmdMsg):
    cmd=CmdCode([0xE7, 0x51])
    x: AbsValue
    y: AbsValue
        
@dataclass
class LayerCount(CmdMsg):
    cmd=CmdCode([0xCA, 0x22])
    layer_count: Layer

@dataclass
class LightRed(CmdMsg):
    cmd=CmdCode([0xD8, 0x00])

@dataclass
class E738(CmdMsg):
    cmd=CmdCode([0xe7, 0x38, 0x00])

@dataclass
class F0(CmdMsg):
    cmd=CmdCode(0xF0)

@dataclass
class E704(CmdMsg):
    cmd=CmdCode([0xE7, 0x04])
    a: Unknown2
    b: Unknown2
    x: AbsValue
    y: AbsValue
        
@dataclass
class E705(CmdMsg):
    cmd=CmdCode([0xE7, 0x05, 0x00])
    
@dataclass
class PenYOffset(CmdMsg):
    cmd=CmdCode([0xE7, 0x54])
    device:Device
    y: AbsValue
        
@dataclass
class LaserYOffset(CmdMsg):
    cmd=CmdCode([0xE7, 0x55])
    device:Device
    y: AbsValue
    
@dataclass
class E732(CmdMsg):
    cmd=CmdCode([0xE7, 0x32])
    x: AbsValue
    y: AbsValue

@dataclass
class F200(CmdMsg):
    cmd=CmdCode([0xF2, 0x00, 0x00])

@dataclass
class Offset(CmdMsg):
    cmd=CmdCode([0xF1, 0x03])
    x: AbsValue
    y: AbsValue

@dataclass
class Offset2(CmdMsg):
    cmd=CmdCode([0xF2, 0x03])
    x: AbsValue
    y: AbsValue
        

@dataclass
class BottomRight(CmdMsg):
    cmd=CmdCode([0xF2, 0x04])
    x: AbsValue
    y: AbsValue

@dataclass
class F205(CmdMsg):
    cmd=CmdCode([0xF2, 0x05])
    a: Unknown2
    b: Unknown2
    x: AbsValue
    y: AbsValue
        
@dataclass
class E717(CmdMsg):
    cmd=CmdCode([0xE7, 0x17])
    a: AbsValue
    b: AbsValue
    
    
@dataclass
class E713(CmdMsg):
    cmd=CmdCode([0xE7, 0x13])
    a: AbsValue
    b: AbsValue
    
@dataclass
class E723(CmdMsg):
    cmd=CmdCode([0xE7, 0x23])
    a: AbsValue
    b: AbsValue
    
@dataclass
class E737(CmdMsg):
    cmd=CmdCode([0xE7, 0x37])
    a: AbsValue
    b: AbsValue

@dataclass
class E708(CmdMsg):
    cmd=CmdCode([0xE7, 0x08])
    unknown_a: Unknown2
    unknown_b: Unknown2
    x: AbsValue
    y: AbsValue
    
@dataclass
class E700(CmdMsg):
    cmd=CmdCode([0xE7, 0x00])
        
@dataclass
class Finish(CmdMsg):
    cmd=CmdCode(0xEB)
    
@dataclass
class E4(CmdMsg):
    cmd=CmdCode(0xE4)

@dataclass
class EOF(CmdMsg):
    cmd=CmdCode(0xD7)

@dataclass
class F206(CmdMsg):
    cmd=CmdCode([0xF2, 0x06])
    x: AbsValue
    y: AbsValue
        
@dataclass
class DA01(CmdMsg):
    cmd=CmdCode([0xDA, 0x01])
    a: Unknown2
    x: AbsValue
    y: AbsValue
        
@dataclass
class E70A(CmdMsg):
    cmd=CmdCode([0xE7, 0x0A])
    a: AbsValue
    
@dataclass
class E760(CmdMsg):
    cmd=CmdCode([0xE7, 0x60, 0x00, 0x00])
    
@dataclass
class E70B(CmdMsg):
    cmd=CmdCode([0xE7, 0x0B, 0x00])

@dataclass
class E724(CmdMsg):
    cmd=CmdCode([0xE7, 0x24, 0x00])
        
@dataclass
class F207(CmdMsg):
    cmd=CmdCode([0xF2, 0x07, 0x00])
        
@dataclass
class EA00(CmdMsg):
    cmd=CmdCode([0xEA, 0x00])

@dataclass
class E300(CmdMsg):
    cmd=CmdCode([0xE3, 0x00])
        
@dataclass
class F208(CmdMsg):
    cmd=CmdCode([0xF2, 0x08])
    x: AbsValue
    y: AbsValue
        
@dataclass
class Start0(CmdMsg):
    cmd=CmdCode([0xF1, 0x00, 0x00])
    
@dataclass
class Start1(CmdMsg):
    cmd=CmdCode([0xF1, 0x01, 0x00])
    
@dataclass
class Start2(CmdMsg):
    cmd=CmdCode([0xF1, 0x02, 0x00])
        
@dataclass
class LayerData:
    color: Tuple[float] = (0, 0, 0)
    layer: int = 0
    min_power: int = 0
    max_power: int = 0
    speed: int = 0
    x_min: int = 0
    y_min: int = 0
    x_max: int = 0
    y_max: int = 0
    
    def to_msg(self):
        msgs = [
            LayerSpeed.from_values(layer=self.layer, speed = self.speed),
            LayerLaser1MinPower.from_values(layer=self.layer, power=self.min_power),
            LayerLaser1MaxPower.from_values(layer=self.layer, power=self.max_power),
            LayerLaser2MinPower.from_values(layer=self.layer, power=self.min_power),
            LayerLaser2MaxPower.from_values(layer=self.layer, power=self.max_power),
            LayerColor.from_values(layer=self.layer, color=(int(self.color[0] * 255) |
                                                            int(self.color[1] * 255) << 8|
                                                            int(self.color[2] * 255) << 16)),
            LayerCA41.from_values(layer=self.layer, u0=0),
            LayerLaser1TopLeft.from_values(layer=self.layer, x=self.x_min, y=self.y_min),
            LayerLaser1BottomRight.from_values(layer=self.layer, x=self.x_max, y=self.y_max),
            LayerLaser2TopLeft.from_values(layer=self.layer, x=self.x_min, y=self.y_min),
            LayerLaser2BottomRight.from_values(layer=self.layer, x=self.x_max, y=self.y_max)]
        return msgs
    
    def change_header(self):
        msgs = [
            EnableDevice.from_values(device=0x00),
            ChangeLayer.from_values(layer=self.layer),
            EnableDevice.from_values(device=0x30),
            EnableDevice.from_values(device=0x10),
            EnableDevice.from_values(device=0x13),
            CutOpenDelay.from_values(ms=0),
            CutCloseDelay.from_values(ms=0),
            CA03.from_values(unknown=0x3F),
            CA10.from_values(unknown=0x00),
        ]
        return msgs
        
def header(width, height, layers):
    unpacked_msgs = [
        UploadFollows.from_values(),
        F0.from_values(),
        Start2.from_values(),
        LightRed.from_values(),
        Feedrate.from_values(x=0, y=0),
        E738.from_values(),
        Laser1TopLeft.from_values(x=0, y=0),
        Laser1BottomRight.from_values(x=width, y=height),
        Laser2TopLeft.from_values(x=0, y=0),
        Laser2BottomRight.from_values(x=width, y=height),
        E704.from_values(a=1, b=1, x=0, y=0),
        E705.from_values(),
    ]

    for layer in layers:
        unpacked_msgs += layer.to_msg()

    unpacked_msgs += [  
        LayerCount.from_values(layer_count=len(layers)-1),
        PenYOffset.from_values  (device=0, y=0),
        PenYOffset.from_values  (device=1, y=0),
        LaserYOffset.from_values(device=0, y=0),
        LaserYOffset.from_values(device=1, y=0),
        Offset.from_values(x=0, y=0),
        Start0.from_values(),
        Start1.from_values(),
        F200.from_values(),
        Offset2.from_values(x=0, y=0),
        BottomRight.from_values(x=width, y=height),
        F205.from_values(a=1, b=1, x=width, y=height),
        F206.from_values(x=0, y=0),
        F207.from_values(),
        F208.from_values(x=width, y=height),
        E70A.from_values(a=0),
        EA00.from_values(),
        E760.from_values(),
        E300.from_values(),
        E70B.from_values(),
        E713.from_values(a=0, b=0),
        E717.from_values(a=width, b=height),
        E723.from_values(a=0, b=0),
        E724.from_values(),
        E737.from_values(a=width, b=height),
        E708.from_values(unknown_a=1, unknown_b=1, x=width, y=height)
    ]
    return unpacked_msgs

def scale_power(x):
    # limit all use cases to 90 % 
    return int(x * 0.90 / 0.0061)

def footer(width, height):
    
    return [
        E4.from_values(),
        Finish.from_values(),
        E700.from_values(),
        DA01.from_values(a=800, x=width, y=height),
        EOF.from_values(),
    ]
    
class LaserSimulator:
        
    def __init__(self):
        self.fig = plt.figure(figsize=(30,20))
        self.ax = self.fig.add_axes([0.05, 0.05, 0.9, 0.9])
        self.x = 0
        self.y = 0
        self.layers = {}
        self.current_layer = 0
    
    def set_layer_property(self, layer, **kargs):
        if layer not in self.layers:
            self.layers[layer] = LayerData(layer=layer)
        for k, v in kargs.items():
            setattr(self.layers[layer], k, v)
    
    def move(self, x, y, cut=False, relative=False):
        old_x = self.x
        old_y = self.y
        if relative:
            self.x += x
            self.y += y
        else:
            self.x = x
            self.y = y
        if cut:
            self.ax.plot([old_x, self.x], [old_y, self.y], c=self.layers[self.current_layer].color)

    def show(self):
        self.ax.axis("equal")
        self.ax.invert_xaxis()
        self.ax.invert_yaxis()
        self.ax.grid()

def unscramble(data, magic=0x88):
    result = []
    for i in data:
        a = (i + 0xFF) & 0xFF
        b = a ^ magic
        result.append((b & 0x7E) | ((b >> 7) & 0x01) | ((b << 7) & 0x80))
    return result

def scramble(data, magic=0x88):
    result = []
    for i in data:
        a = (i & 0x7E) | ((i >> 7) & 0x01) | ((i << 7) & 0x80)
        b = a ^ magic
        result.append((b + 1) & 0xFF)
    return result

def split_msg(data):
    msgs = []
    current_msg = []
    for i in data:
        if i & 0x80 and current_msg:
            msgs.append(current_msg)
            current_msg = []
        current_msg.append(i)
    if current_msg:
        msgs.append(current_msg)
    return msgs


def parse_msgs(msgs):
    lut = {}
    for i in CmdMsg.__subclasses__():
        if i.cmd.length == 1:
            lut[i.cmd.code[0]] = i
        else:
            if i.cmd.code[0] not in lut:
                lut[i.cmd.code[0]] = {}
            lut[i.cmd.code[0]][i.cmd.code[1]] = i

    commands = []
    for i in msgs:
        if i[0] in lut:
            if isinstance(lut[i[0]], dict):
                if i[1] in lut[i[0]]:
                    commands.append(lut[i[0]][i[1]].parse(i))
                    continue
            else:
                commands.append(lut[i[0]].parse(i))
                continue
        commands.append(i)

    return commands


def main():
    filename = sys.argv[1]
    with open(filename, "rb") as f:
        data = unscramble(f.read())
    cmds = parse_msgs(split_msg(data))
    laser_sim = LaserSimulator()
    for i in cmds:
        if not isinstance(i, CmdMsg):
            print([f"0x{u:02x}" for u in i])
        else:
            print(i)
            i.update(laser_sim)
    laser_sim.show()
    repacked = []
    for i in cmds:
        if not isinstance(i, CmdMsg):
            repacked += i
        else:
            repacked += i.pack()
    
    out_filename = sys.argv[2]
    with open(out_filename, "wb") as f:
        f.write(bytearray(scramble(repacked)))
    return

if __name__ == "__main__":
    # execute only if run as a script
    main()

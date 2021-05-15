from typing import Tuple, Optional, List
import dataclasses
import numpy as np
import random

import decode


@dataclasses.dataclass
class point:
    x: float
    y: float


@dataclasses.dataclass
class line:
    layer: int
    a: point
    b: point
    def length(self):
        return np.hypot(self.a.x - self.b.x, self.a.y - self.b.y)
    
@dataclasses.dataclass
class layer:
    power: float  # 0-100 % power
    speed: float  # in mm/s
    color: Tuple[float]  # (r,g,b) 0-1 fraction of color
    pieces: List[List[line]]


def CopyPiece(piece):
    new_piece = []
    for i in piece:
        new_piece.append(line(layer=i.layer,
                              a=point(x=i.a.x, y=i.a.y),
                              b=point(x=i.b.x, y=i.b.y)))
    return new_piece


def TranslatePiece(piece, dx, dy):
    for i in piece:
        i.a.x += dx
        i.a.y += dy
        i.b.x += dx
        i.b.y += dy


def ParseDxfLine(l):
    assert l[0][1] == "LINE"
    layer = ""
    a = point(0, 0)
    b = point(0, 0)
    for i in l[1:]:
        if int(i[0]) == 8:
            layer = i[1]
        if int(i[0]) == 10:
            a.x = float(i[1])
        if int(i[0]) == 20:
            a.y = float(i[1])
        if int(i[0]) == 11:
            b.x = float(i[1])
        if int(i[0]) == 21:
            b.y = float(i[1])
    return line(layer, a, b)


def ParserDxf(data):
    entry = [i.split() for i in data.split(bytes([32]).decode("utf-8")) if i]

    entity_blocks = []
    for i in entry:
        if int(i[0]) == 0:
            entity_blocks.append([])
        entity_blocks[-1].append(i)

    sections = {}
    last_section = None
    for i in entity_blocks:
        if i[0][1] == "SECTION":
            assert int(i[1][0]) == 2
            last_section = i[1][1]
            sections[last_section] = []
            continue
        if i[0][1] == "ENDSEC":
            last_section = None
            continue
        if last_section:
            sections[last_section].append(i)
    
    entities = []
    for i in sections["ENTITIES"]:
        entities.append(ParseDxfLine(i))

    return entities


def PointToLineDist(l:line, p: point):
    l2 = np.square(np.hypot(l.a.x - l.b.x, l.a.y - l.b.y))
    if l == 0:
        return np.hypot(p.x - l.b.x, p.y - l.b.y)
    t = ((p.x - l.a.x) * (l.b.x - l.a.x) + (p.y - l.a.y) * (l.b.y - l.a.y)) / l2
    if t < 0:
        t = 0;
    if t > 1:
        t = 1
    return np.hypot(p.x - (l.a.x + t * (l.b.x - l.a.x)),
                    p.y - (l.a.y + t * (l.b.y - l.a.y)))


def LineOverlap(i, j, delta = 0.35):
    if (PointToLineDist(i, j.a) < delta and
        PointToLineDist(i, j.b) < delta):
        return True
    if (PointToLineDist(j, i.a) < delta and
        PointToLineDist(j, i.b) < delta):
        return True
    for a, b in [(i.a, j.a), (i.b, j.b), (i.a, j.b), (i.b, j.a)]:
        if (PointToLineDist(i, b) < delta and
            PointToLineDist(j, a) < delta and
            np.hypot(a.x - b.x, a.y - b.y) > (np.min([i.length(),
                                                      j.length()])*0.7)):
            return True
    return False


def SplitToPieces(lines):
    pieces = [[]]
    for i in lines:
        if pieces[-1] and pieces[-1][-1].b != i.a:
            pieces.append([])
        pieces[-1].append(i)
    return pieces


def CreateLaserCutData(layers):
    
    min_x = np.nan
    min_y = np.nan
    max_x = np.nan
    max_y = np.nan
    for layer in layers:
        for pieces in layer.pieces:
            for line in pieces:
                for point in [line.a, line.b]:
                    min_x = np.nanmin([min_x, point.x])
                    min_y = np.nanmin([min_y, point.y])
                    max_x = np.nanmax([max_x, point.x])
                    max_y = np.nanmax([max_y, point.y])
    
    layer_headers = []
    
    for i, layer in enumerate(layers):
        layer_headers.append(decode.LayerData(
            color=layer.color,
            layer=i,
            min_power=decode.scale_power(layer.power),
            max_power=decode.scale_power(layer.power),
            speed= (layer.speed) * 1000,
            x_min=0, y_min=0,
            x_max=int((max_x - min_x) * 1000), y_max=int((max_y - min_y) * 1000)))


    unpacked_msgs = decode.header(int((max_x - min_x) * 1000), int((max_y - min_y) * 1000), layer_headers)

    for i, layer in enumerate(layers):
        unpacked_msgs += layer_headers[i].change_header()
        for x in layer.pieces:
            unpacked_msgs +=[decode.MoveAbs.from_values(x=int((x[0].a.x-min_x) * 1000.0), y=int((x[0].a.y - min_y) * 1000.0))]
            for j in x:
                unpacked_msgs += [
                    decode.CutAbs.from_values(x=int((j.b.x - min_x) * 1000.0), y=int((j.b.y - min_y) * 1000.0))]

    unpacked_msgs += decode.footer(80,80)

    repacked = []

    for i in unpacked_msgs:
        if isinstance(i, decode.CmdMsg):
            repacked += i.pack()
            continue
        repacked += i

    return bytearray(decode.scramble(repacked))
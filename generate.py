#!/usr/bin/env python3
"""Generate Harmonic Beacon 6-band spatializer Pd patches with UI controls."""

import os

class PdPatch:
    def __init__(self, x, y, w, h, font=12):
        self.header = f"#N canvas {x} {y} {w} {h} {font};"
        self.items = []
        self.conns = []
        self.names = {}

    def _add(self, name, kind, x, y, *args):
        if name and name in self.names:
            raise ValueError(f"duplicate name: {name}")
        idx = len(self.items)
        if name:
            self.names[name] = idx
        self.items.append((kind, x, y, args))
        return idx

    def obj(self, name, x, y, *args):
        return self._add(name, "obj", x, y, *args)

    def msg(self, name, x, y, *args):
        text = " ".join(str(a) for a in args)
        return self._add(name, "msg", x, y, text)

    def fatom(self, name, x, y, width=5, lower=0, upper=0):
        self.items.append(("fatom", x, y, (width, lower, upper, 0, "-", "-", "-")))
        idx = len(self.items) - 1
        if name:
            self.names[name] = idx
        return idx

    def text(self, x, y, text):
        self.items.append(("text", x, y, (text,)))
        return len(self.items) - 1

    def connect(self, src, src_out, dst, dst_in):
        self.conns.append((src, src_out, dst, dst_in))

    def save(self, path):
        lines = [self.header]
        for kind, x, y, args in self.items:
            if kind == "text":
                lines.append(f"#X text {x} {y} {args[0]};")
            elif kind == "obj":
                text = " ".join(str(a) for a in args)
                lines.append(f"#X obj {x} {y} {text};")
            elif kind == "msg":
                lines.append(f"#X msg {x} {y} {args[0]};")
            elif kind == "fatom":
                w, lo, hi, lp, lbl, rcv, snd = args
                lines.append(f"#X floatatom {x} {y} {w} {lo} {hi} {lp} {lbl} {rcv} {snd};")
        for src, src_out, dst, dst_in in self.conns:
            src_idx = self.names[src]
            dst_idx = self.names[dst]
            lines.append(f"#X connect {src_idx} {src_out} {dst_idx} {dst_in};")
        with open(path, "w") as f:
            f.write("\n".join(lines))


def build_spatializer():
    p = PdPatch(100, 100, 500, 400)

    p.obj("in_sig",   30,  30, "inlet~", "signal")
    p.obj("in_az",   180,  30, "inlet", "azimuth")
    p.obj("in_dist", 320,  30, "inlet", "distance")
    p.obj("out_l",    30, 350, "outlet~", "left")
    p.obj("out_r",   180, 350, "outlet~", "right")

    p.obj("sin_az", 180, 100, "expr", "sin($f1 * 3.14159 / 180)")
    p.obj("tfff",   180, 140, "t", "f", "f", "f")

    p.obj("gain_l", 100, 180, "expr", "sqrt((1 - $f1) / 2)")
    p.obj("gain_r", 260, 180, "expr", "sqrt((1 + $f1) / 2)")

    p.obj("itd_mul", 180, 180, "*", 0.65)
    p.obj("moses",   180, 220, "moses", 0)
    p.obj("abs_r",   140, 260, "*", -1)

    p.obj("dist_gain", 320, 100, "expr", "1 / $f1")
    p.obj("mul_gl",    100, 260, "*", 1)
    p.obj("mul_gr",    260, 260, "*", 1)

    p.obj("dwrite", 30, 120, "delwrite~", "$0-buf", 5)
    p.obj("dread_l", 30, 260, "delread~", "$0-buf", 0)
    p.obj("dread_r", 180, 260, "delread~", "$0-buf", 0)

    p.obj("amp_l", 30, 320, "*~")
    p.obj("amp_r", 180, 320, "*~")

    p.connect("in_sig",  0, "dwrite",   0)
    p.connect("in_az",   0, "sin_az",   0)
    p.connect("sin_az",  0, "tfff",     0)
    p.connect("tfff",    0, "gain_l",   0)
    p.connect("tfff",    1, "gain_r",   0)
    p.connect("tfff",    2, "itd_mul",  0)
    p.connect("itd_mul", 0, "moses",    0)
    p.connect("moses",   0, "abs_r",    0)
    p.connect("moses",   1, "dread_l",  0)
    p.connect("abs_r",   0, "dread_r",  0)
    p.connect("in_dist", 0, "dist_gain",0)
    p.connect("dist_gain",0,"mul_gl",   1)
    p.connect("dist_gain",0,"mul_gr",   1)
    p.connect("gain_l",  0, "mul_gl",   0)
    p.connect("gain_r",  0, "mul_gr",   0)
    p.connect("mul_gl",  0, "amp_l",    1)
    p.connect("mul_gr",  0, "amp_r",    1)
    p.connect("dread_l", 0, "amp_l",    0)
    p.connect("dread_r", 0, "amp_r",    0)
    p.connect("amp_l",   0, "out_l",    0)
    p.connect("amp_r",   0, "out_r",    0)

    return p


def build_main():
    p = PdPatch(50, 50, 1400, 950)
    p.text(50, 10, "Harmonic Beacon — 6-band spatializer (40Hz series)")
    p.text(50, 30, "Drag number boxes to tweak. Use headphones for binaural effect.")

    p.obj("adc", 50, 80, "adc~", 1)

    bands = [
        (40,  2.67,  180, 2.0, 1.2, "40Hz root"),
        (80,  5.33,  135, 2.5, 1.0, "80Hz"),
        (120, 8.0,   -90, 3.0, 1.0, "120Hz"),
        (160, 10.67, -45, 2.5, 1.0, "160Hz"),
        (200, 13.33,  45, 2.0, 1.0, "200Hz"),
        (240, 16.0,    0, 1.5, 1.3, "240Hz butterfly"),
    ]

    init_targets = []
    x0 = 50
    x_step = 180

    for i, (freq, q, az, dist, gain, label) in enumerate(bands):
        x = x0 + i * x_step
        b = f"b{i+1}"

        p.text(x, 60, label)
        p.obj(f"{b}_bp", x, 100, "bp~", freq, q)

        # gain control (msg + floatatom)
        p.msg(f"{b}_gain_msg", x, 125, gain)
        p.fatom(f"{b}_gain_fa", x, 145, 5, 0, 3)
        p.obj(f"{b}_amp", x, 180, "*~")
        p.connect(f"{b}_gain_msg", 0, f"{b}_gain_fa", 0)
        p.connect(f"{b}_gain_fa", 0, f"{b}_amp", 1)
        init_targets.append(f"{b}_gain_msg")

        # flutter on last band
        if i == 5:
            p.obj(f"{b}_flosc", x, 210, "osc~", 3.7)
            p.obj(f"{b}_flscale", x, 235, "*~", 0.15)
            p.obj(f"{b}_floffset", x, 260, "+~", 0.85)
            p.obj(f"{b}_flutter", x, 290, "*~")

        # azimuth control
        p.msg(f"{b}_az_msg", x, 320, az)
        p.fatom(f"{b}_az_fa", x, 340, 5, -180, 180)
        p.connect(f"{b}_az_msg", 0, f"{b}_az_fa", 0)
        init_targets.append(f"{b}_az_msg")

        # distance control
        p.msg(f"{b}_dist_msg", x+70, 320, dist)
        p.fatom(f"{b}_dist_fa", x+70, 340, 5, 0, 10)
        p.connect(f"{b}_dist_msg", 0, f"{b}_dist_fa", 0)
        init_targets.append(f"{b}_dist_msg")

        # spatializer
        p.obj(f"{b}_spat", x, 390, "spatializer~")

        # signal chain
        p.connect("adc", 0, f"{b}_bp", 0)
        p.connect(f"{b}_bp", 0, f"{b}_amp", 0)

        if i == 5:
            p.connect(f"{b}_amp", 0, f"{b}_flutter", 0)
            p.connect(f"{b}_flosc", 0, f"{b}_flscale", 0)
            p.connect(f"{b}_flscale", 0, f"{b}_floffset", 0)
            p.connect(f"{b}_floffset", 0, f"{b}_flutter", 1)
            p.connect(f"{b}_flutter", 0, f"{b}_spat", 0)
        else:
            p.connect(f"{b}_amp", 0, f"{b}_spat", 0)

        p.connect(f"{b}_az_fa", 0, f"{b}_spat", 1)
        p.connect(f"{b}_dist_fa", 0, f"{b}_spat", 2)

    # LFO for band 6 azimuth
    lfo_x = 1150
    p.obj("lfo_lb", lfo_x, 100, "loadbang")
    p.msg("lfo_rate_msg", lfo_x, 130, "0.08")
    p.obj("lfo_osc", lfo_x, 160, "osc~")
    p.obj("lfo_scale", lfo_x, 200, "*~", 90)
    p.obj("lfo_sum", lfo_x, 280, "+~")
    p.text(lfo_x + 10, 60, "240Hz LFO")

    p.msg("lfo_off_msg", lfo_x + 80, 130, "0")
    p.fatom("lfo_off_fa", lfo_x + 80, 150, 5, -180, 180)
    p.obj("lfo_sig", lfo_x + 80, 190, "sig~")
    p.connect("lfo_off_msg", 0, "lfo_off_fa", 0)
    p.connect("lfo_off_fa", 0, "lfo_sig", 0)
    init_targets.extend(["lfo_rate_msg", "lfo_off_msg"])

    p.obj("lfo_metro", lfo_x, 320, "metro", 20)
    p.obj("lfo_snap", lfo_x, 350, "snapshot~")

    p.connect("lfo_lb", 0, "lfo_rate_msg", 0)
    p.connect("lfo_rate_msg", 0, "lfo_osc", 0)
    p.connect("lfo_osc", 0, "lfo_scale", 0)
    p.connect("lfo_scale", 0, "lfo_sum", 0)
    p.connect("lfo_sig", 0, "lfo_sum", 1)
    p.connect("lfo_lb", 0, "lfo_metro", 0)
    p.connect("lfo_metro", 0, "lfo_snap", 0)
    p.connect("lfo_sum", 0, "lfo_snap", 0)
    p.connect("lfo_snap", 0, "b6_spat", 1)

    # sum all left outputs
    p.obj("sum_la", 50, 480, "+~")
    p.obj("sum_lb", 230, 480, "+~")
    p.obj("sum_lc", 410, 480, "+~")
    p.obj("sum_ld", 140, 530, "+~")
    p.obj("sum_lall", 275, 590, "+~")

    p.connect("b1_spat", 0, "sum_la", 0)
    p.connect("b2_spat", 0, "sum_la", 1)
    p.connect("b3_spat", 0, "sum_lb", 0)
    p.connect("b4_spat", 0, "sum_lb", 1)
    p.connect("b5_spat", 0, "sum_lc", 0)
    p.connect("b6_spat", 0, "sum_lc", 1)
    p.connect("sum_la", 0, "sum_ld", 0)
    p.connect("sum_lb", 0, "sum_ld", 1)
    p.connect("sum_ld", 0, "sum_lall", 0)
    p.connect("sum_lc", 0, "sum_lall", 1)

    # sum all right outputs
    p.obj("sum_ra", 50, 510, "+~")
    p.obj("sum_rb", 230, 510, "+~")
    p.obj("sum_rc", 410, 510, "+~")
    p.obj("sum_rd", 140, 560, "+~")
    p.obj("sum_rall", 275, 620, "+~")

    p.connect("b1_spat", 1, "sum_ra", 0)
    p.connect("b2_spat", 1, "sum_ra", 1)
    p.connect("b3_spat", 1, "sum_rb", 0)
    p.connect("b4_spat", 1, "sum_rb", 1)
    p.connect("b5_spat", 1, "sum_rc", 0)
    p.connect("b6_spat", 1, "sum_rc", 1)
    p.connect("sum_ra", 0, "sum_rd", 0)
    p.connect("sum_rb", 0, "sum_rd", 1)
    p.connect("sum_rd", 0, "sum_rall", 0)
    p.connect("sum_rc", 0, "sum_rall", 1)

    # dry/wet mix with UI
    p.text(600, 590, "MIX")
    p.msg("wet_msg", 600, 620, "0.85")
    p.fatom("wet_fa", 600, 640, 5, 0, 1)
    p.msg("dry_msg", 660, 620, "0.3")
    p.fatom("dry_fa", 660, 640, 5, 0, 1)
    p.obj("wet_l", 600, 680, "*~")
    p.obj("wet_r", 660, 680, "*~")
    p.obj("dry_l", 720, 680, "*~")
    p.obj("dry_r", 780, 680, "*~")

    p.connect("wet_msg", 0, "wet_fa", 0)
    p.connect("dry_msg", 0, "dry_fa", 0)
    init_targets.extend(["wet_msg", "dry_msg"])

    p.connect("sum_lall", 0, "wet_l", 0)
    p.connect("sum_rall", 0, "wet_r", 0)
    p.connect("wet_fa", 0, "wet_l", 1)
    p.connect("wet_fa", 0, "wet_r", 1)
    p.connect("adc", 0, "dry_l", 0)
    p.connect("adc", 0, "dry_r", 0)
    p.connect("dry_fa", 0, "dry_l", 1)
    p.connect("dry_fa", 0, "dry_r", 1)

    # final mix
    p.obj("final_l", 600, 740, "+~")
    p.obj("final_r", 750, 740, "+~")

    p.connect("wet_l", 0, "final_l", 0)
    p.connect("dry_l", 0, "final_l", 1)
    p.connect("wet_r", 0, "final_r", 0)
    p.connect("dry_r", 0, "final_r", 1)

    # master gain with UI
    p.msg("master_msg", 600, 780, "0.9")
    p.fatom("master_fa", 600, 800, 5, 0, 2)
    p.obj("master_l", 600, 840, "*~")
    p.obj("master_r", 750, 840, "*~")
    p.obj("dac", 600, 890, "dac~", 1, 2)

    p.connect("master_msg", 0, "master_fa", 0)
    p.connect("master_fa", 0, "master_l", 1)
    p.connect("master_fa", 0, "master_r", 1)
    p.connect("final_l", 0, "master_l", 0)
    p.connect("final_r", 0, "master_r", 0)
    p.connect("master_l", 0, "dac", 0)
    p.connect("master_r", 0, "dac", 1)
    init_targets.append("master_msg")

    # OSC remote control (UDP + oscparse)
    p.text(950, 450, "OSC remote control (UDP port 9001)")
    p.obj("netrcv", 950, 470, "iemnet/udpreceive", 9001)
    p.obj("oscparse", 950, 500, "oscparse")
    p.obj("oscprint", 950, 520, "print", "osc_in")
    p.obj("osc_route", 950, 550, "route", "/beacon/gain/1", "/beacon/az/1", "/beacon/dist/1",
          "/beacon/gain/2", "/beacon/az/2", "/beacon/dist/2",
          "/beacon/gain/3", "/beacon/az/3", "/beacon/dist/3",
          "/beacon/gain/4", "/beacon/az/4", "/beacon/dist/4",
          "/beacon/gain/5", "/beacon/az/5", "/beacon/dist/5",
          "/beacon/gain/6", "/beacon/az/6", "/beacon/dist/6",
          "/beacon/wet", "/beacon/dry", "/beacon/master", "/beacon/lfo/offset")
    p.connect("netrcv", 0, "oscparse", 0)
    p.connect("oscparse", 0, "oscprint", 0)
    p.connect("oscparse", 0, "osc_route", 0)

    # Map OSC outputs to floatatoms (visual) and audio objects (actual control)
    osc_targets = [
        (0,  "b1_gain_fa", [("b1_amp", 1)]),
        (1,  "b1_az_fa",   [("b1_spat", 1)]),
        (2,  "b1_dist_fa", [("b1_spat", 2)]),
        (3,  "b2_gain_fa", [("b2_amp", 1)]),
        (4,  "b2_az_fa",   [("b2_spat", 1)]),
        (5,  "b2_dist_fa", [("b2_spat", 2)]),
        (6,  "b3_gain_fa", [("b3_amp", 1)]),
        (7,  "b3_az_fa",   [("b3_spat", 1)]),
        (8,  "b3_dist_fa", [("b3_spat", 2)]),
        (9,  "b4_gain_fa", [("b4_amp", 1)]),
        (10, "b4_az_fa",   [("b4_spat", 1)]),
        (11, "b4_dist_fa", [("b4_spat", 2)]),
        (12, "b5_gain_fa", [("b5_amp", 1)]),
        (13, "b5_az_fa",   [("b5_spat", 1)]),
        (14, "b5_dist_fa", [("b5_spat", 2)]),
        (15, "b6_gain_fa", [("b6_amp", 1)]),
        (16, "b6_az_fa",   [("b6_spat", 1)]),
        (17, "b6_dist_fa", [("b6_spat", 2)]),
        (18, "wet_fa",     [("wet_l", 1), ("wet_r", 1)]),
        (19, "dry_fa",     [("dry_l", 1), ("dry_r", 1)]),
        (20, "master_fa",  [("master_l", 1), ("master_r", 1)]),
        (21, "lfo_off_fa", [("lfo_sig", 0)]),
    ]
    for idx, fa_name, audio_dests in osc_targets:
        p.connect("osc_route", idx, fa_name, 0)
        for obj_name, inlet in audio_dests:
            p.connect("osc_route", idx, obj_name, inlet)

    # init loadbang
    p.obj("lb_init", 1000, 80, "loadbang")
    p.msg("dsp_on", 1000, 110, "pd dsp 1")
    p.connect("lb_init", 0, "dsp_on", 0)

    for t in init_targets:
        p.connect("lb_init", 0, t, 0)

    return p


if __name__ == "__main__":
    out = os.path.expanduser("~/Projects/beacon-spatial")
    os.makedirs(out, exist_ok=True)
    build_spatializer().save(os.path.join(out, "spatializer~.pd"))
    build_main().save(os.path.join(out, "beacon-spatial.pd"))
    print(f"Patches written to {out}")

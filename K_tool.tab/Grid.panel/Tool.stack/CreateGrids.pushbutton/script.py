# -*- coding: utf-8 -*-
"""Create Revit grids from a spacing syntax (e.g. 5x5000+7x7500+2x5000)
or from lines on a layer of a linked/imported CAD file.

pyRevit pushbutton (IronPython 2.7 / CPython). Units in the form are mm.
"""
__title__ = "Create\nGrids"
__author__ = "Khoa Le"

import re
import clr
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
import System.Windows.Forms as WF
import System.Drawing as SD

from Autodesk.Revit.DB import (Grid, Line, XYZ, Transaction, ImportInstance,
                               GraphicsStyle, Options, GeometryInstance,
                               PolyLine, FilteredElementCollector)
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
MM = 1.0 / 304.8          # mm -> feet
TOL = 1e-6


# ----------------------------------------------------------------- helpers
def parse_spacing(text):
    """'5x5000+7x7500+2x5000' -> [5000]*5 + [7500]*7 + [5000]*2.
    Accepts x, X, *, and separators '+', ',', ';' or spaces."""
    result = []
    text = (text or "").strip()
    if not text:
        return result
    for token in re.split(r"[+,;\s]+", text):
        if not token:
            continue
        m = re.match(r"^(\d+)\s*[xX*@]\s*(\d+(?:\.\d+)?)$", token)
        if m:
            result += [float(m.group(2))] * int(m.group(1))
        elif re.match(r"^\d+(?:\.\d+)?$", token):
            result.append(float(token))
        else:
            raise ValueError("Cannot read '{}'".format(token))
    return result


def letter_labels(start, count, skip="IO"):
    """A, B, ... Z, AA, AB ... skipping I and O."""
    def to_str(n):
        s = ""
        n += 1
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s
    out, n = [], 0
    # find start index
    while to_str(n) != start.upper() and n < 10000:
        n += 1
    if n >= 10000:
        n = 0
    while len(out) < count:
        s = to_str(n)
        if not any(c in skip for c in s):
            out.append(s)
        n += 1
    return out


def make_labels(start, count):
    start = (start or "1").strip()
    if re.match(r"^\d+$", start):
        return [str(int(start) + i) for i in range(count)]
    return letter_labels(start, count)


def existing_grid_names():
    return set(g.Name for g in FilteredElementCollector(doc).OfClass(Grid))


def safe_name(grid, name, used):
    if name in used:
        name = name + "'"
        while name in used:
            name += "'"
    try:
        grid.Name = name
        used.add(name)
    except Exception:
        pass


# ------------------------------------------------------- syntax grid mode
def create_from_syntax(x_txt, y_txt, x_start, y_start, ext_mm, origin):
    xs = parse_spacing(x_txt)
    ys = parse_spacing(y_txt)
    x_pos = [0.0]
    for s in xs:
        x_pos.append(x_pos[-1] + s)
    y_pos = [0.0]
    for s in ys:
        y_pos.append(y_pos[-1] + s)
    if not xs:
        x_pos = [0.0] if x_txt.strip() == "0" else []
    if not ys:
        y_pos = [0.0] if y_txt.strip() == "0" else []

    ext = ext_mm
    xmin, xmax = (min(x_pos) if x_pos else 0) - ext, (max(x_pos) if x_pos else 0) + ext
    ymin, ymax = (min(y_pos) if y_pos else 0) - ext, (max(y_pos) if y_pos else 0) + ext

    used = existing_grid_names()
    ox, oy, oz = origin.X, origin.Y, origin.Z
    count = 0
    t = Transaction(doc, "Create Grids (syntax)")
    t.Start()
    # vertical grids along X  (numbered 1, 2, 3 ...)
    for x, name in zip(x_pos, make_labels(x_start, len(x_pos))):
        p0 = XYZ(ox + x * MM, oy + ymin * MM, oz)
        p1 = XYZ(ox + x * MM, oy + ymax * MM, oz)
        safe_name(Grid.Create(doc, Line.CreateBound(p0, p1)), name, used)
        count += 1
    # horizontal grids along Y  (lettered A, B, C ...)
    for y, name in zip(y_pos, make_labels(y_start, len(y_pos))):
        p0 = XYZ(ox + xmin * MM, oy + y * MM, oz)
        p1 = XYZ(ox + xmax * MM, oy + y * MM, oz)
        safe_name(Grid.Create(doc, Line.CreateBound(p0, p1)), name, used)
        count += 1
    t.Commit()
    return count


# ---------------------------------------------------------- CAD link mode
class CadFilter(ISelectionFilter):
    def AllowElement(self, e):
        return isinstance(e, ImportInstance)

    def AllowReference(self, r, p):
        return False


def cad_lines(cad):
    """Return {layer_name: [Line, ...]} in project coordinates."""
    opt = Options()
    opt.IncludeNonVisibleObjects = False
    layers = {}

    def add(curve_list, style_id):
        style = doc.GetElement(style_id)
        name = style.GraphicsStyleCategory.Name if isinstance(style, GraphicsStyle) else "?"
        layers.setdefault(name, []).extend(curve_list)

    for g in cad.get_Geometry(opt):
        if not isinstance(g, GeometryInstance):
            continue
        for obj in g.GetInstanceGeometry():       # already transformed
            if isinstance(obj, Line):
                add([obj], obj.GraphicsStyleId)
            elif isinstance(obj, PolyLine):
                pts = list(obj.GetCoordinates())
                segs = []
                for a, b in zip(pts[:-1], pts[1:]):
                    if a.DistanceTo(b) > 0.01:
                        segs.append(Line.CreateBound(a, b))
                add(segs, obj.GraphicsStyleId)
    return layers


def merge_collinear(lines):
    """Merge overlapping / collinear segments so one grid per axis line."""
    groups = []
    for ln in lines:
        p0, p1 = ln.GetEndPoint(0), ln.GetEndPoint(1)
        p0 = XYZ(p0.X, p0.Y, 0)
        p1 = XYZ(p1.X, p1.Y, 0)
        if p0.DistanceTo(p1) < 0.01:
            continue
        d = (p1 - p0).Normalize()
        if d.X < -TOL or (abs(d.X) < TOL and d.Y < 0):   # canonical direction
            d = d.Negate()
        placed = False
        for g in groups:
            gd, gp = g["d"], g["p"]
            if abs(abs(gd.DotProduct(d)) - 1) < 1e-4 and \
               abs(gd.CrossProduct(p0 - gp).Z) < 0.01:   # same line (~3mm)
                g["t"] += [gd.DotProduct(p0 - gp), gd.DotProduct(p1 - gp)]
                placed = True
                break
        if not placed:
            groups.append({"d": d, "p": p0,
                           "t": [0.0, d.DotProduct(p1 - p0)]})
    result = []
    for g in groups:
        a, b = min(g["t"]), max(g["t"])
        result.append((g["d"], g["p"] + g["d"] * a, g["p"] + g["d"] * b))
    return result


def create_from_cad(layer_lines, x_start, y_start, ext_mm, z):
    axes = merge_collinear(layer_lines)
    ext = ext_mm * MM
    # split into "numbered" (more vertical) and "lettered" (more horizontal)
    vert = [a for a in axes if abs(a[0].Y) > abs(a[0].X)]
    horz = [a for a in axes if abs(a[0].Y) <= abs(a[0].X)]
    vert.sort(key=lambda a: (a[1].X + a[2].X))
    horz.sort(key=lambda a: (a[1].Y + a[2].Y))

    used = existing_grid_names()
    t = Transaction(doc, "Create Grids (CAD)")
    t.Start()
    for group, labels in ((vert, make_labels(x_start, len(vert))),
                          (horz, make_labels(y_start, len(horz)))):
        for (d, p0, p1), name in zip(group, labels):
            a = XYZ(p0.X, p0.Y, z) - d * ext
            b = XYZ(p1.X, p1.Y, z) + d * ext
            safe_name(Grid.Create(doc, Line.CreateBound(a, b)), name, used)
    t.Commit()
    return len(vert) + len(horz)


# --------------------------------------------------------------------- UI
class GridForm(WF.Form):
    def __init__(self):
        self.Text = "Create Grids"
        self.Width, self.Height = 460, 400
        self.FormBorderStyle = WF.FormBorderStyle.FixedDialog
        self.StartPosition = WF.FormStartPosition.CenterScreen
        self.result = None
        y = [12]

        def row(label, default, width=300):
            lb = WF.Label(Text=label, Left=12, Top=y[0] + 3, Width=120)
            tb = WF.TextBox(Text=default, Left=135, Top=y[0], Width=width)
            self.Controls.Add(lb)
            self.Controls.Add(tb)
            y[0] += 30
            return tb

        hint = WF.Label(Left=12, Top=y[0], Width=420, Height=32,
                        Text="Syntax: n x spacing joined by '+', mm.  "
                             "e.g. 5x5000+7x7500+2x5000   or  6000+8000+6000")
        self.Controls.Add(hint)
        y[0] += 38
        self.tx = row("X spacing (1,2,3..):", "5x5000+7x7500+2x5000")
        self.ty = row("Y spacing (A,B,C..):", "4x6000")
        self.sx = row("First X label:", "1", 80)
        self.sy = row("First Y label:", "A", 80)
        self.ext = row("Extension (mm):", "2000", 80)
        self.pick = WF.CheckBox(Text="Pick origin point in view (else 0,0)",
                                Left=135, Top=y[0], Width=300, Checked=True)
        self.Controls.Add(self.pick)
        y[0] += 40

        b1 = WF.Button(Text="Create from syntax", Left=12, Top=y[0], Width=200, Height=32)
        b2 = WF.Button(Text="Create from CAD link...", Left=230, Top=y[0], Width=200, Height=32)
        b1.Click += lambda s, e: self._done("syntax")
        b2.Click += lambda s, e: self._done("cad")
        self.Controls.Add(b1)
        self.Controls.Add(b2)

    def _done(self, mode):
        if mode == "syntax":
            try:
                parse_spacing(self.tx.Text)
                parse_spacing(self.ty.Text)
            except ValueError as ex:
                WF.MessageBox.Show(str(ex), "Syntax error")
                return
        self.result = mode
        self.Close()


def choose_layer(layers):
    f = WF.Form(Text="Select grid layer", Width=360, Height=420,
                StartPosition=WF.FormStartPosition.CenterScreen)
    lb = WF.ListBox(Left=10, Top=10, Width=325, Height=320)
    names = sorted(layers.keys(), key=lambda n: (-("GRID" in n.upper() or "AXIS" in n.upper()), n))
    for n in names:
        lb.Items.Add("{}  ({} lines)".format(n, len(layers[n])))
    if names:
        lb.SelectedIndex = 0
    ok = WF.Button(Text="OK", Left=10, Top=340, Width=325, Height=30)
    ok.Click += lambda s, e: f.Close()
    f.Controls.Add(lb)
    f.Controls.Add(ok)
    f.ShowDialog()
    return names[lb.SelectedIndex] if lb.SelectedIndex >= 0 else None


def main():
    form = GridForm()
    form.ShowDialog()
    if not form.result:
        return
    try:
        ext = float(form.ext.Text)
    except ValueError:
        ext = 2000.0
    z = doc.ActiveView.GenLevel.Elevation if doc.ActiveView.GenLevel else 0.0

    if form.result == "syntax":
        origin = XYZ(0, 0, z)
        if form.pick.Checked:
            try:
                p = uidoc.Selection.PickPoint("Pick grid origin (intersection of first grids)")
                origin = XYZ(p.X, p.Y, z)
            except Exception:
                return
        n = create_from_syntax(form.tx.Text, form.ty.Text,
                               form.sx.Text, form.sy.Text, ext, origin)
    else:
        try:
            ref = uidoc.Selection.PickObject(ObjectType.Element, CadFilter(),
                                             "Select CAD link / import")
        except Exception:
            return
        layers = cad_lines(doc.GetElement(ref))
        if not layers:
            WF.MessageBox.Show("No lines found in the CAD file.")
            return
        layer = choose_layer(layers)
        if not layer:
            return
        n = create_from_cad(layers[layer], form.sx.Text, form.sy.Text, ext, z)

    WF.MessageBox.Show("{} grids created.".format(n), "Create Grids")


main()

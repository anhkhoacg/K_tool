# -*- coding: utf-8 -*-
"""Grid Mark - write the nearest grid intersection (e.g. A-3) into a text
parameter (default: Mark) of the selected elements.

- Uses the selection; if nothing is selected, asks for categories and runs
  on all elements of those categories in the active view.
- Duplicate codes get a lowercase suffix (A-3a, A-3b, ... A-3aa) that does not
  clash with marks already used by other elements of the same categories.
- Elements further than the tolerance from a grid get OFF-GRID.
  Shift+Click the button to set the tolerance.
"""
__title__ = "Grid\nMark"
__author__ = "Khoa Le"

from System.Collections.Generic import List
from pyrevit import revit, DB, forms, script

doc = revit.doc
out = script.get_output()
cfg = script.get_config()

MM = 1.0 / 304.8          # mm -> feet
SEP = "-"
OFF_GRID = "OFF-GRID"

CATEGORIES = [
    ("Structural Foundations", DB.BuiltInCategory.OST_StructuralFoundation),
    ("Structural Columns", DB.BuiltInCategory.OST_StructuralColumns),
    ("Columns", DB.BuiltInCategory.OST_Columns),
    ("Generic Models", DB.BuiltInCategory.OST_GenericModel),
    ("Structural Framing", DB.BuiltInCategory.OST_StructuralFraming),
    ("Walls", DB.BuiltInCategory.OST_Walls),
]


# ----------------------------------------------------------------- helpers
def eid(element_id):
    """ElementId -> int (Revit 2024+ uses .Value)."""
    try:
        return element_id.Value
    except AttributeError:
        return element_id.IntegerValue


def xy(p):
    return DB.XYZ(p.X, p.Y, 0)


def is_number(name):
    return name.strip().isdigit()


def letter_suffix(i):
    """0 -> a, 25 -> z, 26 -> aa, 27 -> ab ..."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(97 + r) + s
    return s


def el_point(el):
    loc = el.Location
    if isinstance(loc, DB.LocationPoint):
        return xy(loc.Point)
    if isinstance(loc, DB.LocationCurve):
        return xy(loc.Curve.Evaluate(0.5, True))
    bb = el.get_BoundingBox(None)
    if bb:
        return xy((bb.Min + bb.Max) / 2.0)
    return None


# ----------------------------------------------------------------- grids
class GridLine(object):
    """Straight grid, made unbound in XY for perpendicular distance."""
    def __init__(self, grid):
        c = grid.Curve
        self.name = grid.Name
        d = xy(c.Direction).Normalize()
        self.dir = d
        self.line = DB.Line.CreateUnbound(xy(c.GetEndPoint(0)), d)

    def dist(self, pt):
        return self.line.Project(pt).Distance


def collect_grids():
    grids = [GridLine(g) for g in DB.FilteredElementCollector(doc).OfClass(DB.Grid)
             if isinstance(g.Curve, DB.Line)]
    grids.sort(key=lambda g: g.name)       # repeatable tie-breaks
    num = [g for g in grids if is_number(g.name)]
    let = [g for g in grids if not is_number(g.name)]
    if num and let:
        return let, num

    # fallback: split by direction relative to the first grid
    if not grids:
        return [], []
    ref = grids[0].dir
    fam_a = [g for g in grids if abs(g.dir.DotProduct(ref)) > 0.7]
    fam_b = [g for g in grids if abs(g.dir.DotProduct(ref)) <= 0.7]
    # put the family with alphabetic names first, else the ~Y-direction one
    if any(not is_number(g.name) for g in fam_b) and \
            all(is_number(g.name) for g in fam_a):
        return fam_b, fam_a
    return fam_a, fam_b


def nearest(gs, pt):
    best, best_d = None, None
    for g in gs:
        d = g.dist(pt)
        if best_d is None or d < best_d - 1e-9:
            best, best_d = g, d
    return best, best_d


# ----------------------------------------------------------------- inputs
def get_elements():
    sel = revit.get_selection().elements
    if sel:
        return list(sel)

    names = forms.SelectFromList.show(
        [n for n, _ in CATEGORIES],
        title="Grid Mark - nothing selected: pick categories (active view)",
        multiselect=True, button_name="Use these categories")
    if not names:
        script.exit()
    view_id = doc.ActiveView.Id
    els = []
    for n, bic in CATEGORIES:
        if n in names:
            els.extend(DB.FilteredElementCollector(doc, view_id)
                       .OfCategory(bic).WhereElementIsNotElementType()
                       .ToElements())
    return els


let_grids, num_grids = collect_grids()
if not let_grids or not num_grids:
    forms.alert("Need straight grids in two directions "
                "(letters and numbers).", exitscript=True)

els = get_elements()
if not els:
    forms.alert("No elements to process.", exitscript=True)

param_name = forms.ask_for_string(
    default=cfg.get_option("param_name", "Mark"),
    prompt="Target text parameter:",
    title="Grid Mark")
if not param_name:
    script.exit()
param_name = param_name.strip()

overwrite = forms.alert("Overwrite existing values?\n\n"
                        "No = only fill empty parameters.",
                        title="Grid Mark", yes=True, no=True)

cfg.param_name = param_name
script.save_config()

tol_mm = float(cfg.get_option("tolerance_mm", 1500))
tol_ft = tol_mm * MM


# ----------------------------------------------------------------- 1) codes
groups = {}
skipped = []          # (element id, reason)

for el in els:
    p = el.LookupParameter(param_name)
    if p is None:
        skipped.append((el.Id, "no parameter '{}'".format(param_name)))
        continue
    if p.StorageType != DB.StorageType.String:
        skipped.append((el.Id, "parameter is not text"))
        continue
    if p.IsReadOnly:
        skipped.append((el.Id, "parameter is read-only"))
        continue
    if el.GroupId != DB.ElementId.InvalidElementId:
        skipped.append((el.Id, "element is in a group"))
        continue
    if not overwrite and p.AsString():
        skipped.append((el.Id, "already has a value"))
        continue
    pt = el_point(el)
    if pt is None:
        skipped.append((el.Id, "no location"))
        continue

    g_let, d_let = nearest(let_grids, pt)
    g_num, d_num = nearest(num_grids, pt)
    if tol_ft > 0 and (d_let > tol_ft or d_num > tol_ft):
        code = OFF_GRID
    else:
        code = "{}{}{}".format(g_let.name, SEP, g_num.name)
    groups.setdefault(code, []).append((pt, el, p))


# ------------------------------------------- marks already used elsewhere
to_write = set(eid(el.Id) for items in groups.values() for _, el, _ in items)

used = set()
if groups:
    # Revit warns on duplicate Mark within a category -> scan those categories
    id_list = List[DB.ElementId]()
    for items in groups.values():
        for _, el, _ in items:
            if el.Category and not id_list.Contains(el.Category.Id):
                id_list.Add(el.Category.Id)
    collector = DB.FilteredElementCollector(doc) \
        .WherePasses(DB.ElementMulticategoryFilter(id_list)) \
        .WhereElementIsNotElementType()
    for e in collector:
        if eid(e.Id) in to_write:
            continue
        q = e.LookupParameter(param_name)
        if q and q.StorageType == DB.StorageType.String and q.AsString():
            used.add(q.AsString())


# ----------------------------------------------------------------- 2) write
results = []          # (element id, mark)
with revit.Transaction("Grid Location Mark"):
    for code in sorted(groups):
        items = groups[code]
        items.sort(key=lambda t: (round(t[0].X, 3), round(t[0].Y, 3)))
        need_suffix = len(items) > 1 or code in used
        i = 0
        for pt, el, p in items:
            mark = code
            if need_suffix:
                while True:
                    mark = code + letter_suffix(i)
                    i += 1
                    if mark not in used:
                        break
            p.Set(mark)
            used.add(mark)
            results.append((el.Id, mark))


# ----------------------------------------------------------------- report
out.print_md("## Grid Mark")
out.print_md("**Parameter:** {}  |  **Tolerance:** {} mm  |  "
             "**Updated:** {}  |  **Skipped:** {}".format(
                 param_name, tol_mm if tol_mm > 0 else "off",
                 len(results), len(skipped)))
if results:
    out.print_table([[out.linkify(i), m] for i, m in results],
                    columns=["Element", param_name], title="Updated")
if skipped:
    out.print_table([[out.linkify(i), r] for i, r in skipped],
                    columns=["Element", "Reason"], title="Skipped")

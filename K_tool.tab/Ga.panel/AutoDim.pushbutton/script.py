# -*- coding: utf-8 -*-
"""
Auto Dim

Place basic GA dimensions on the selected elements in the active
plan / section / elevation view:
    - a chain dimension through every face edge-on in the view,
    - an overall dimension (outer face to outer face),
for the horizontal direction (below or above the element) and the
vertical direction (left or right of the element).

Only planar faces that are seen edge-on (normal parallel to the view's
Right or Up direction) are dimensioned. Coplanar faces are merged.
Offsets are given in paper millimetres and scaled by the view scale.

Shift+Click to change offsets.

Compatible with IronPython 2.7 and CPython 3 (pyRevit), Revit 2024+.
"""

from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter

from pyrevit import revit, DB, forms, script, EXEC_PARAMS


doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView
output = script.get_output()


# ============================================================
# SETTINGS
# ============================================================

# Paper distances (mm on the printed sheet), scaled by view scale
FIRST_OFFSET_PAPER_MM = 8.0     # element edge -> first dimension line
SPACING_PAPER_MM = 7.0          # between chain line and overall line

# Faces closer than this along the dimension axis are merged (model mm)
MERGE_TOL_MM = 1.0

# Normal must be within this of the axis (cosine)
PARALLEL_COS = 0.9999

VIEW_TYPES_OK = (
    DB.ViewType.FloorPlan,
    DB.ViewType.CeilingPlan,
    DB.ViewType.EngineeringPlan,
    DB.ViewType.AreaPlan,
    DB.ViewType.Section,
    DB.ViewType.Elevation,
    DB.ViewType.Detail,
)

OPT_H_CHAIN = "Horizontal - chain"
OPT_H_OVERALL = "Horizontal - overall"
OPT_V_CHAIN = "Vertical - chain"
OPT_V_OVERALL = "Vertical - overall"
OPT_H_TOP = "Place horizontal dims ABOVE (default below)"
OPT_V_RIGHT = "Place vertical dims on the RIGHT (default left)"

OPTIONS = [
    (OPT_H_CHAIN, True),
    (OPT_H_OVERALL, True),
    (OPT_V_CHAIN, True),
    (OPT_V_OVERALL, True),
    (OPT_H_TOP, False),
    (OPT_V_RIGHT, False),
]


# ============================================================
# HELPERS
# ============================================================

def mm(value_mm):
    return DB.UnitUtils.ConvertToInternalUnits(
        value_mm, DB.UnitTypeId.Millimeters)


def to_mm(value_ft):
    return DB.UnitUtils.ConvertFromInternalUnits(
        value_ft, DB.UnitTypeId.Millimeters)


class ModelElementFilter(ISelectionFilter):
    def AllowElement(self, element):
        return (element.Category is not None
                and element.Category.CategoryType == DB.CategoryType.Model
                and not isinstance(element, DB.Group))

    def AllowReference(self, ref, point):
        return False


def get_elements():
    ids = list(uidoc.Selection.GetElementIds())
    if ids:
        elements = [doc.GetElement(i) for i in ids]
    else:
        try:
            with forms.WarningBar(title="Select elements to dimension, "
                                        "then click Finish"):
                refs = uidoc.Selection.PickObjects(
                    ObjectType.Element, ModelElementFilter(),
                    "Select elements to dimension")
        except Exception:
            script.exit()
        elements = [doc.GetElement(r) for r in refs]
    return [e for e in elements
            if e is not None and e.Category is not None
            and e.Category.CategoryType == DB.CategoryType.Model]


# ============================================================
# GEOMETRY
# ============================================================

class FaceData(object):
    """A planar face usable as a dimension reference."""

    def __init__(self, reference, normal, origin):
        self.reference = reference
        self.normal = normal
        self.origin = origin


def iter_solids(geometry, transform, out_faces, out_points):
    """
    Walk geometry. For a GeometryInstance use the SYMBOL geometry
    (its references are valid for dimensioning) and carry the instance
    transform to get world positions.
    """
    if geometry is None:
        return
    for obj in geometry:
        if isinstance(obj, DB.GeometryInstance):
            iter_solids(obj.GetSymbolGeometry(),
                        transform.Multiply(obj.Transform),
                        out_faces, out_points)
        elif isinstance(obj, DB.Solid):
            if obj.Faces.Size == 0 or obj.Volume < 1e-9:
                continue
            for face in obj.Faces:
                if not isinstance(face, DB.PlanarFace):
                    continue
                if face.Reference is None:
                    continue
                out_faces.append(FaceData(
                    face.Reference,
                    transform.OfVector(face.FaceNormal).Normalize(),
                    transform.OfPoint(face.Origin)))
            for edge in obj.Edges:
                for p in edge.Tessellate():
                    out_points.append(transform.OfPoint(p))


def get_geometry(element):
    options = DB.Options()
    options.ComputeReferences = True
    options.IncludeNonVisibleObjects = False
    options.View = view
    faces, points = [], []
    iter_solids(element.get_Geometry(options), DB.Transform.Identity,
                faces, points)
    return faces, points


def unique_stations(faces, axis, tol):
    """
    Faces whose normal is parallel to `axis`, merged by position along
    the axis. Returns sorted list of (position, reference).
    """
    found = []
    for f in faces:
        if abs(f.normal.DotProduct(axis)) < PARALLEL_COS:
            continue
        pos = f.origin.DotProduct(axis)
        if any(abs(pos - p) < tol for p, _r in found):
            continue
        found.append((pos, f.reference))
    found.sort(key=lambda item: item[0])
    return found


def ref_array(stations):
    arr = DB.ReferenceArray()
    for _pos, ref in stations:
        arr.Append(ref)
    return arr


# ============================================================
# DIMENSION PLACEMENT
# ============================================================

def view_point(u, v):
    """Point in the view plane from (Right, Up) coordinates."""
    origin = view.Origin
    o_u = origin.DotProduct(right)
    o_v = origin.DotProduct(up)
    return origin.Add(right.Multiply(u - o_u)).Add(up.Multiply(v - o_v))


def make_dim(stations, along, line_offset_coord):
    """
    along = "H": dimension line parallel to Right at v = line_offset_coord
    along = "V": dimension line parallel to Up    at u = line_offset_coord
    """
    first, last = stations[0][0], stations[-1][0]
    if along == "H":
        p0 = view_point(first, line_offset_coord)
        p1 = view_point(last, line_offset_coord)
    else:
        p0 = view_point(line_offset_coord, first)
        p1 = view_point(line_offset_coord, last)
    line = DB.Line.CreateBound(p0, p1)
    return doc.Create.NewDimension(view, line, ref_array(stations))


def try_dim(element, label, stations, along, coord, created, failures):
    sub = DB.SubTransaction(doc)
    try:
        sub.Start()
        dim = make_dim(stations, along, coord)
        if dim is None:
            raise Exception("Revit returned no dimension")
        sub.Commit()
        created.append((element, label, dim,
                        int(round(to_mm(stations[-1][0] - stations[0][0])))))
        return True
    except Exception as error:
        if sub.GetStatus() == DB.TransactionStatus.Started:
            sub.RollBack()
        failures.append((element, "{}: {}".format(label, error)))
        return False


# ============================================================
# MAIN
# ============================================================

if view.ViewType not in VIEW_TYPES_OK:
    forms.alert("Open a plan, section or elevation view first.\n"
                "(3D views and sheets are not supported.)",
                exitscript=True)

first_paper = FIRST_OFFSET_PAPER_MM
spacing_paper = SPACING_PAPER_MM
if EXEC_PARAMS.config_mode:  # Shift+Click
    text = forms.ask_for_string(
        default="{}, {}".format(first_paper, spacing_paper),
        prompt="Paper offsets in mm: first line, spacing",
        title="Auto Dim")
    if text is None:
        script.exit()
    try:
        first_paper, spacing_paper = [float(t) for t in text.split(",")]
    except Exception:
        forms.alert("Invalid input: {}".format(text), exitscript=True)

chosen = forms.SelectFromList.show(
    [forms.TemplateListItem(name, checked=on) for name, on in OPTIONS],
    title="Auto Dim - what to dimension",
    multiselect=True,
    button_name="Next")
if not chosen:
    script.exit()
chosen = set(chosen)

elements = get_elements()
if not elements:
    forms.alert("No model elements selected.", exitscript=True)

right = view.RightDirection.Normalize()
up = view.UpDirection.Normalize()
scale = max(view.Scale, 1)
first_off = mm(first_paper) * scale
spacing = mm(spacing_paper) * scale
tol = mm(MERGE_TOL_MM)

h_sign = 1.0 if OPT_H_TOP in chosen else -1.0
v_sign = 1.0 if OPT_V_RIGHT in chosen else -1.0

created = []
failures = []
skipped = []

with revit.Transaction("Auto Dim"):
    for el in elements:
        try:
            faces, points = get_geometry(el)
        except Exception as error:
            skipped.append((el, "geometry: {}".format(error)))
            continue
        if not faces or not points:
            skipped.append((el, "no planar faces visible in this view"))
            continue

        us = [p.DotProduct(right) for p in points]
        vs = [p.DotProduct(up) for p in points]
        u_min, u_max = min(us), max(us)
        v_min, v_max = min(vs), max(vs)

        h_st = unique_stations(faces, right, tol)   # positions along Right
        v_st = unique_stations(faces, up, tol)      # positions along Up

        # ---- horizontal (dimension line parallel to Right) ----
        h_base = v_max if h_sign > 0 else v_min
        if len(h_st) >= 2:
            level = 0
            if OPT_H_CHAIN in chosen and len(h_st) > 2:
                coord = h_base + h_sign * (first_off + level * spacing)
                if try_dim(el, "H chain", h_st, "H", coord,
                           created, failures):
                    level += 1
            if OPT_H_OVERALL in chosen:
                coord = h_base + h_sign * (first_off + level * spacing)
                try_dim(el, "H overall", [h_st[0], h_st[-1]], "H", coord,
                        created, failures)
        elif OPT_H_CHAIN in chosen or OPT_H_OVERALL in chosen:
            skipped.append((el, "horizontal: fewer than 2 edge-on faces"))

        # ---- vertical (dimension line parallel to Up) ----
        v_base = u_max if v_sign > 0 else u_min
        if len(v_st) >= 2:
            level = 0
            if OPT_V_CHAIN in chosen and len(v_st) > 2:
                coord = v_base + v_sign * (first_off + level * spacing)
                if try_dim(el, "V chain", v_st, "V", coord,
                           created, failures):
                    level += 1
            if OPT_V_OVERALL in chosen:
                coord = v_base + v_sign * (first_off + level * spacing)
                try_dim(el, "V overall", [v_st[0], v_st[-1]], "V", coord,
                        created, failures)
        elif OPT_V_CHAIN in chosen or OPT_V_OVERALL in chosen:
            skipped.append((el, "vertical: fewer than 2 edge-on faces"))


# ============================================================
# REPORT
# ============================================================

if failures or skipped:
    output.print_md("# Auto Dim")
    output.print_md("**Dimensions created:** {} &nbsp;|&nbsp; "
                    "**Failures:** {} &nbsp;|&nbsp; **Skipped:** {}".format(
                        len(created), len(failures), len(skipped)))
    if created:
        output.print_table(
            [[output.linkify(e.Id), lbl, output.linkify(d.Id), length]
             for e, lbl, d, length in created],
            columns=["Element", "Dim", "Dimension", "Overall (mm)"],
            title="Created")
    if failures:
        output.print_table(
            [[output.linkify(e.Id), m] for e, m in failures],
            columns=["Element", "Error"], title="Failures")
    if skipped:
        output.print_table(
            [[output.linkify(e.Id), m] for e, m in skipped],
            columns=["Element", "Reason"], title="Skipped")
elif not created:
    forms.alert("No dimensions were created.")

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

Option: use the reference planes of family instances (Strong / Weak /
Left / Right / Front / Back / Top / Bottom / Center...) as extra
dimension references, or instead of faces. Planes set to
"Not a Reference" in the family are not exposed by Revit and are
ignored. A plane's position is measured with a temporary dimension
to a temporary detail line (both rolled back), so it is correct for
every type / instance size and for mirrored instances.

Offsets are given in paper millimetres and scaled by the view scale.

Shift+Click to choose what to dimension and the offsets (config.py).
A normal click runs with the saved settings, without any dialog.

Compatible with IronPython 2.7 and CPython 3 (pyRevit), Revit 2024+.
"""

from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter

from pyrevit import revit, DB, forms, script


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

# Option keys saved by config.py (Shift+Click), with their defaults.
# Keep in sync with OPTIONS in config.py.
OPT_H_CHAIN = "h_chain"
OPT_H_OVERALL = "h_overall"
OPT_V_CHAIN = "v_chain"
OPT_V_OVERALL = "v_overall"
OPT_H_TOP = "h_top"
OPT_V_RIGHT = "v_right"
OPT_REF_PLANES = "ref_planes"
OPT_PLANES_ONLY = "planes_only"
OPT_NO_WEAK = "no_weak"

OPTION_DEFAULTS = [
    (OPT_H_CHAIN, True),
    (OPT_H_OVERALL, True),
    (OPT_V_CHAIN, True),
    (OPT_V_OVERALL, True),
    (OPT_H_TOP, False),
    (OPT_V_RIGHT, False),
    (OPT_REF_PLANES, True),
    (OPT_PLANES_ONLY, False),
    (OPT_NO_WEAK, True),
]

# Distance of the temporary anchor line from the element (feet).
# Must be larger than how far any reference plane sits outside the
# element's geometry.
ANCHOR_MARGIN_FT = 500.0

# FamilyInstanceReferenceType values collected as reference planes
PLANE_REF_TYPES = [
    "Left", "CenterLeftRight", "Right",
    "Front", "CenterFrontBack", "Back",
    "Bottom", "CenterElevation", "Top",
    "StrongReference", "WeakReference",
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


def face_stations(faces, axis):
    """(position, reference) of faces whose normal is parallel to axis."""
    return [(f.origin.DotProduct(axis), f.reference) for f in faces
            if abs(f.normal.DotProduct(axis)) >= PARALLEL_COS]


def merge_stations(stations, tol):
    """
    Drop stations closer than tol to an earlier one (earlier entries
    win), then sort by position.
    """
    found = []
    for pos, ref in stations:
        if any(abs(pos - p) < tol for p, _r in found):
            continue
        found.append((pos, ref))
    found.sort(key=lambda item: item[0])
    return found


# ============================================================
# FAMILY REFERENCE PLANES
# ============================================================

def get_family_plane_refs(element, skip_weak=False):
    """All reference-plane references a family instance exposes."""
    if not isinstance(element, DB.FamilyInstance):
        return []
    refs, seen = [], set()
    for type_name in PLANE_REF_TYPES:
        if skip_weak and type_name == "WeakReference":
            continue
        ref_type = getattr(DB.FamilyInstanceReferenceType, type_name, None)
        if ref_type is None:
            continue
        try:
            found = element.GetReferences(ref_type)
        except Exception:
            continue
        for ref in found:
            try:
                key = ref.ConvertToStableRepresentation(doc)
            except Exception:
                continue
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs


def anchor_line(along, coord, span_lo, span_hi):
    """
    Temporary detail line used as a dimension anchor.
    along = "H": anchor for horizontal dims = line parallel to Up at u=coord
    along = "V": anchor for vertical dims   = line parallel to Right at v=coord
    """
    if along == "H":
        line = DB.Line.CreateBound(view_point(coord, span_lo),
                                   view_point(coord, span_hi))
    else:
        line = DB.Line.CreateBound(view_point(span_lo, coord),
                                   view_point(span_hi, coord))
    return doc.Create.NewDetailCurve(view, line)


def measure_plane_stations(plane_refs, u_min, u_max, v_min, v_max):
    """
    Measure where each reference plane sits along Right and Up.

    For each axis a temporary detail line is drawn perpendicular to the
    axis, far before the element; a temporary dimension from that line
    to the plane gives the plane's position. Planes not parallel to the
    anchor make NewDimension fail and are skipped for that axis.
    Everything is rolled back.

    Returns (h_stations, v_stations) as lists of (position, reference).
    """
    h_found, v_found = [], []
    if not plane_refs:
        return h_found, v_found

    u0 = u_min - ANCHOR_MARGIN_FT
    v0 = v_min - ANCHOR_MARGIN_FT

    sub = DB.SubTransaction(doc)
    sub.Start()
    try:
        h_anchor = anchor_line("H", u0, v_min, v_max)
        v_anchor = anchor_line("V", v0, u_min, u_max)
        h_anchor_ref = h_anchor.GeometryCurve.Reference
        v_anchor_ref = v_anchor.GeometryCurve.Reference

        pending = []   # (axis, origin coord, dimension, plane ref)
        for ref in plane_refs:
            for axis, anchor_ref, origin in (("H", h_anchor_ref, u0),
                                             ("V", v_anchor_ref, v0)):
                arr = DB.ReferenceArray()
                arr.Append(anchor_ref)
                arr.Append(ref)
                if axis == "H":
                    line = DB.Line.CreateBound(view_point(u0, v0),
                                               view_point(u0 + 1.0, v0))
                else:
                    line = DB.Line.CreateBound(view_point(u0, v0),
                                               view_point(u0, v0 + 1.0))
                try:
                    dim = doc.Create.NewDimension(view, line, arr)
                except Exception:
                    dim = None
                if dim is not None:
                    pending.append((axis, origin, dim, ref))

        doc.Regenerate()
        for axis, origin, dim, ref in pending:
            try:
                value = dim.Value
            except Exception:
                value = None
            if value is None or value < 1e-6:
                continue
            target = h_found if axis == "H" else v_found
            target.append((origin + value, ref))
    finally:
        sub.RollBack()
    return h_found, v_found


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

# Settings come from the button config (Shift+Click -> config.py)
cfg = script.get_config()


def as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


chosen = set(key for key, default in OPTION_DEFAULTS
             if as_bool(cfg.get_option(key, default)))
try:
    first_paper = float(cfg.get_option("first_paper_mm",
                                       FIRST_OFFSET_PAPER_MM))
    spacing_paper = float(cfg.get_option("spacing_paper_mm",
                                         SPACING_PAPER_MM))
except (TypeError, ValueError):
    first_paper, spacing_paper = FIRST_OFFSET_PAPER_MM, SPACING_PAPER_MM

if not chosen & set([OPT_H_CHAIN, OPT_H_OVERALL, OPT_V_CHAIN,
                     OPT_V_OVERALL]):
    forms.alert("No dimensions are enabled.\n"
                "Shift+Click the button to choose what to dimension.",
                exitscript=True)

elements = get_elements()
if not elements:
    forms.alert("No model elements selected.", exitscript=True)

right = view.RightDirection.Normalize()
up = view.UpDirection.Normalize()
scale = max(view.Scale, 1)
first_off = mm(first_paper) * scale
spacing = mm(spacing_paper) * scale
tol = mm(MERGE_TOL_MM)

planes_only = OPT_PLANES_ONLY in chosen
use_planes = planes_only or OPT_REF_PLANES in chosen
skip_weak = OPT_NO_WEAK in chosen

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
        if not points:
            skipped.append((el, "no geometry visible in this view"))
            continue

        us = [p.DotProduct(right) for p in points]
        vs = [p.DotProduct(up) for p in points]
        u_min, u_max = min(us), max(us)
        v_min, v_max = min(vs), max(vs)

        # Reference planes first so they win over coincident faces
        h_raw, v_raw = [], []
        if use_planes:
            plane_refs = get_family_plane_refs(el, skip_weak)
            if plane_refs:
                try:
                    h_raw, v_raw = measure_plane_stations(
                        plane_refs, u_min, u_max, v_min, v_max)
                except Exception as error:
                    failures.append((el, "reference planes: {}".format(
                        error)))
            if planes_only and not h_raw and not v_raw:
                skipped.append((el, "no usable reference planes "
                                    "(not a family, or all set to "
                                    "Not a Reference)"))
        if not planes_only:
            h_raw += face_stations(faces, right)
            v_raw += face_stations(faces, up)

        h_st = merge_stations(h_raw, tol)   # positions along Right
        v_st = merge_stations(v_raw, tol)   # positions along Up

        # Keep dims clear of planes that sit outside the geometry
        if h_st:
            u_min = min(u_min, h_st[0][0])
            u_max = max(u_max, h_st[-1][0])
        if v_st:
            v_min = min(v_min, v_st[0][0])
            v_max = max(v_max, v_st[-1][0])

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

# -*- coding: utf-8 -*-
# pyRevit: For each selected element, compute centroid and create 3 colored axis model lines (X/Y/Z).
# Line total length is ALWAYS 100mm (regardless of project units).

from Autodesk.Revit.DB import (
    Options, ViewDetailLevel, Solid, GeometryInstance, Transform,
    XYZ, Line, Plane, SketchPlane, Transaction, UnitUtils, Color,
    BuiltInCategory, GraphicsStyleType
)
from Autodesk.Revit.UI import TaskDialog

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document


# ============================================================
# Convert 100mm to internal units (feet) - robust across versions
# ============================================================
def mm_to_internal(mm_val):
    """Convert millimeters to internal Revit units (feet), supporting multiple Revit versions."""
    try:
        # Revit 2021+
        from Autodesk.Revit.DB import UnitTypeId
        return UnitUtils.ConvertToInternalUnits(float(mm_val), UnitTypeId.Millimeters)
    except:
        # Older versions
        try:
            from Autodesk.Revit.DB import DisplayUnitType
            return UnitUtils.ConvertToInternalUnits(float(mm_val), DisplayUnitType.DUT_MILLIMETERS)
        except:
            # Fallback: 1 foot = 304.8 mm
            return float(mm_val) / 304.8


# ============================================================
# Centroid helpers (solid volume-weighted; fallback bbox)
# ============================================================
def _solid_centroid_volume_weighted(geom_elem, current_transform):
    """
    Walk geometry (including GeometryInstance) and compute volume-weighted centroid.
    Returns (centroid_XYZ, total_volume) or (None, 0.0)
    """
    if geom_elem is None:
        return (None, 0.0)

    total_vol = 0.0
    weighted_sum = XYZ(0, 0, 0)

    for gobj in geom_elem:
        if gobj is None:
            continue

        if isinstance(gobj, Solid):
            vol = gobj.Volume
            if vol and vol > 1e-9:
                c_local = gobj.ComputeCentroid()
                c_world = current_transform.OfPoint(c_local)
                weighted_sum = weighted_sum.Add(c_world.Multiply(vol))
                total_vol += vol

        elif isinstance(gobj, GeometryInstance):
            inst_trf = current_transform.Multiply(gobj.Transform)
            inst_geom = gobj.GetInstanceGeometry()
            c_inst, v_inst = _solid_centroid_volume_weighted(inst_geom, inst_trf)
            if c_inst and v_inst > 1e-9:
                weighted_sum = weighted_sum.Add(c_inst.Multiply(v_inst))
                total_vol += v_inst

    if total_vol > 1e-9:
        return (weighted_sum.Divide(total_vol), total_vol)

    return (None, 0.0)


def _bbox_center(elem):
    bb = elem.get_BoundingBox(None)
    if not bb:
        return None
    return (bb.Min + bb.Max) * 0.5


def get_best_centroid(elem):
    """Return (centroidXYZ, methodStr)."""
    opt = Options()
    opt.ComputeReferences = False
    opt.IncludeNonVisibleObjects = False
    opt.DetailLevel = ViewDetailLevel.Fine

    try:
        geom = elem.get_Geometry(opt)
    except:
        geom = None

    c_solid, v = _solid_centroid_volume_weighted(geom, Transform.Identity)
    if c_solid:
        return c_solid, "Solid centroid"

    c_bb = _bbox_center(elem)
    if c_bb:
        return c_bb, "BoundingBox center"

    return None, "No geometry"


# ============================================================
# Line style (subcategory) creation + color assignment
# ============================================================
def get_or_create_axis_linestyles():
    """
    Create/get subcategories under Lines:
      Axis_X (Red), Axis_Y (Green), Axis_Z (Blue)
    Return dict of GraphicsStyle for projection: {"X": gsX, "Y": gsY, "Z": gsZ}
    """
    cats = doc.Settings.Categories
    lines_cat = cats.get_Item(BuiltInCategory.OST_Lines)

    def ensure_subcat(name, rgb):
        # Find existing
        subcat = None
        for sc in lines_cat.SubCategories:
            if sc.Name == name:
                subcat = sc
                break

        # Create if missing
        if subcat is None:
            subcat = cats.NewSubcategory(lines_cat, name)

        # Set color
        subcat.LineColor = Color(rgb[0], rgb[1], rgb[2])

        # Return GraphicsStyle to assign to ModelCurve.LineStyle
        return subcat.GetGraphicsStyle(GraphicsStyleType.Projection)

    gsX = ensure_subcat("Axis_X", (255, 0, 0))  # Red
    gsY = ensure_subcat("Axis_Y", (0, 200, 0))  # Green
    gsZ = ensure_subcat("Axis_Z", (0, 120, 255))  # Blue

    return {"X": gsX, "Y": gsY, "Z": gsZ}


# ============================================================
# Create triad (3 model lines) at a point
# ============================================================
def create_colored_axis_triad(pt, total_len_internal, axis_styles):
    """
    Creates 3 ModelCurves centered at pt:
      X (red), Y (green), Z (blue)
    total_len_internal is the total length in internal units (feet).
    """
    half_len = total_len_internal / 2.0

    # Endpoints
    pX1 = pt - XYZ.BasisX.Multiply(half_len)
    pX2 = pt + XYZ.BasisX.Multiply(half_len)

    pY1 = pt - XYZ.BasisY.Multiply(half_len)
    pY2 = pt + XYZ.BasisY.Multiply(half_len)

    pZ1 = pt - XYZ.BasisZ.Multiply(half_len)
    pZ2 = pt + XYZ.BasisZ.Multiply(half_len)

    # Curves
    lineX = Line.CreateBound(pX1, pX2)
    lineY = Line.CreateBound(pY1, pY2)
    lineZ = Line.CreateBound(pZ1, pZ2)

    # Sketch planes:
    # X and Y lines lie on XY plane -> normal Z
    # Z line lies on XZ plane -> normal Y
    plane_xy = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, pt)
    plane_xz = Plane.CreateByNormalAndOrigin(XYZ.BasisY, pt)

    sp_xy = SketchPlane.Create(doc, plane_xy)
    sp_xz = SketchPlane.Create(doc, plane_xz)

    creator = doc.FamilyCreate if doc.IsFamilyDocument else doc.Create

    mcX = creator.NewModelCurve(lineX, sp_xy)
    mcY = creator.NewModelCurve(lineY, sp_xy)
    mcZ = creator.NewModelCurve(lineZ, sp_xz)

    # Assign line styles (colors)
    mcX.LineStyle = axis_styles["X"]
    mcY.LineStyle = axis_styles["Y"]
    mcZ.LineStyle = axis_styles["Z"]

    return (mcX, mcY, mcZ)


# ============================================================
# Main
# ============================================================
sel_ids = list(uidoc.Selection.GetElementIds())
if not sel_ids:
    TaskDialog.Show("XYZ Triad", "Please select elements first.")
    raise SystemExit

elements = [doc.GetElement(eid) for eid in sel_ids if doc.GetElement(eid)]
elements = [e for e in elements if e is not None]

if not elements:
    TaskDialog.Show("XYZ Triad", "No valid elements in selection.")
    raise SystemExit

# Always 100mm total length
LINE_LENGTH_MM = 100.0
line_len_internal = mm_to_internal(LINE_LENGTH_MM)

t = Transaction(doc, "Create 100mm colored XYZ triads at element centroids")
t.Start()

created = 0
skipped = 0

try:
    axis_styles = get_or_create_axis_linestyles()

    for e in elements:
        c, method = get_best_centroid(e)
        if c is None:
            skipped += 1
            continue

        create_colored_axis_triad(c, line_len_internal, axis_styles)
        created += 1

    t.Commit()

except Exception as ex:
    t.RollBack()
    TaskDialog.Show("Error", str(ex))
    raise

TaskDialog.Show(
    "Done",
    "Created {} triads (one per element).\nSkipped: {}\nLine length: {} mm (always)".format(
        created, skipped, int(LINE_LENGTH_MM)
    )
)

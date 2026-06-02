__title__ = "Multi Rebar Annotation"
__doc__ = (
    """Bulk create MultiRebar Annotation of all rebar on active view.
    -----------------------------------------------
    1. select the Multi rebar annotation type.
    2. select direction by Horizontal or vertical
    """)
__author__ = "khoa.le at Haskoning.com"

from System.Collections.Generic import List
# python
from pyrevit import revit, DB

doc = revit.doc
uidoc = revit.uidoc
# Get target view and elements
view = revit.active_view
active_view_id = view.Id

if view is None:
    raise Exception("No active view found.")

# GET rebar
rebar_groups = list(
    DB.FilteredElementCollector(doc, view.Id)
    .OfClass(DB.Structure.Rebar)
    .WhereElementIsNotElementType()
)
# rebar_list = [r for r in rebar_list if r]
if not rebar_groups:
    raise Exception("There are no rebars in the view!")

# Get annotation type
# Collect all MultiReferenceAnnotationType element types in the document
mra_types = list(
    DB.FilteredElementCollector(doc)
    .OfClass(DB.MultiReferenceAnnotationType)
    .WhereElementIsElementType()
)
if not mra_types:
    raise Exception("No MultiReferenceAnnotationType elements found in the document.")
# UI
# Try to present a selection box to the user (pyrevit.forms). Fall back to first type if unavailable or cancelled.
try:
    from pyrevit import forms
except Exception:
    forms = None


# Build readable choices including ElementId to disambiguate duplicate names
def _safe_name(el):
    # Try several safe ways to obtain a name without triggering MissingMemberException
    try:
        return el.Name
    except Exception:
        pass
    try:
        p = el.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
        if p:
            val = p.AsString()
            if val:
                return val
    except Exception:
        pass
    try:
        p2 = el.LookupParameter("Name")
        if p2:
            val = p2.AsString()
            if val:
                return val
    except Exception:
        pass
    # final fallback
    try:
        return "TypeId:{}".format(int(el.Id.IntegerValue))
    except Exception:
        return "<unnamed>"


choices = ["{0} (Id:{1})".format(_safe_name(t), int(t.Id.IntegerValue)) for t in mra_types]

selected_type = None
if forms:
    sel = forms.SelectFromList.show(choices, title="Select MultiReferenceAnnotationType", width=500)
    if sel:
        # SelectFromList may return a single string or a list; normalize to string
        sel_str = sel if isinstance(sel, str) else (sel[0] if len(sel) else None)
        if sel_str:
            # parse the id portion and match back to the element
            import re

            m = re.search(r"Id:(-?\d+)", sel_str)
            if m:
                sel_id = int(m.group(1))
                selected_type = next((t for t in mra_types if int(t.Id.IntegerValue) == sel_id), None)

# Cancel silently if no selection was made or forms not available
if (forms is None) or (selected_type is None):
    raise SystemExit

# Now use selected_type as the MultiReferenceAnnotationType for the rest of the script
mra_type = selected_type

if mra_type is None:
    raise Exception("The MultiReferenceAnnotationType does not exist!")

# Find the matching UIView for the active view
ui_views = uidoc.GetOpenUIViews()
ui_view = None
for uv in ui_views:
    if uv.ViewId.IntegerValue == active_view_id.IntegerValue:
        ui_view = uv
        break
# chose Direction
if ui_view:
    # GetZoomCorners returns two XYZs in model space (lower-left, upper-right of current zoom)
    p1, p2 = ui_view.GetZoomCorners()
    center_VIEW = (p1 + p2) * 0.5

else:
    print("No matching UIView found for the active view (is it open onscreen?).")

ops = ['Horizontal', 'Vertical']
ops_out = forms.CommandSwitchWindow.show(ops, message='Select Option')

if ops_out == 'Horizontal':
    lineDirection = view.RightDirection
else:
    lineDirection = view.UpDirection

try:
    lineDirection = lineDirection.Normalize()
except Exception:
    pass
#####

with revit.Transaction("Create_RebarGroup_Annotations"):
    for i, rebar in enumerate(rebar_groups):
        # Build a List[ElementId] from the single rebar element (replace invalid GetElementId call)
        rebar_ids = List[DB.ElementId]([rebar.Id])
        if not rebar_ids:
            continue

        options = DB.MultiReferenceAnnotationOptions(mra_type)
        options.TagHasLeader = True
        options.TagHeadPosition = center_VIEW
        # set the dimension line origin to the picked point (or view center fallback)
        options.DimensionLineOrigin = center_VIEW
        options.DimensionLineDirection = lineDirection
        options.DimensionPlaneNormal = view.ViewDirection
        options.SetElementsToDimension(rebar_ids)

        try:
            DB.MultiReferenceAnnotation.Create(doc, view.Id, options)
        except Exception:
            # Ignore rebars that can't be used with the chosen linear dimension direction
            continue

# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import FilteredElementCollector, ViewSection, ViewType, Viewport
from Autodesk.Revit.UI import TaskDialog

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
active_view = doc.ActiveView

viewports = list(FilteredElementCollector(doc).OfClass(Viewport))
sheet_by_view_id = {}
for vp in viewports:
    sheet = doc.GetElement(vp.SheetId)
    if sheet:
        sheet_by_view_id[vp.ViewId.IntegerValue] = "{} - {}".format(sheet.SheetNumber, sheet.Name)

matches = []
for view in FilteredElementCollector(doc).OfClass(ViewSection):
    if view.IsTemplate:
        continue
    if view.OwnerViewId != active_view.Id:
        continue

    is_callout = getattr(view, "IsCallout", False)
    if not is_callout and view.ViewType != ViewType.Section:
        continue

    kind = "Callout" if is_callout else "Section"
    sheet_name = sheet_by_view_id.get(view.Id.IntegerValue, "<Not placed on sheet>")
    matches.append((view.Name or "", kind, sheet_name))

if not matches:
    TaskDialog.Show("Section/Callout Views", "No section or callout views found in current view.")
else:
    matches.sort(key=lambda x: x[0].lower())
    lines = ["{} | {} | {}".format(kind, name, sheet_name) for name, kind, sheet_name in matches]
    TaskDialog.Show(
        "Section/Callout Views",
        "Current View: {}\nCount: {}\n\n{}".format(active_view.Name, len(lines), "\n".join(lines))
    )

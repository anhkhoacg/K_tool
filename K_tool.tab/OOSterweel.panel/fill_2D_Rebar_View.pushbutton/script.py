import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')
from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, Transaction, View, ElementId
)
from Autodesk.Revit.UI import TaskDialog

# get doc & uidoc (try RevitServices first, fallback to __revit__)
doc = None
uidoc = None
try:
    from RevitServices.Persistence import DocumentManager

    uidoc = DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument
    doc = uidoc.Document
except Exception:
    try:
        uidoc = __revit__.ActiveUIDocument  # pyrevit context
        doc = uidoc.Document
    except Exception:
        pass

if doc is None or uidoc is None:
    TaskDialog.Show("Fill 2d_Rebar_view", "No Revit document available.")
else:
    # determine target views: any selected Views, otherwise active view
    selected_view_ids = []
    try:
        sel_ids = uidoc.Selection.GetElementIds()
        for eid in sel_ids:
            el = doc.GetElement(eid)
            if isinstance(el, View):
                selected_view_ids.append(el.Id)
    except Exception:
        selected_view_ids = []

    if selected_view_ids:
        views = [doc.GetElement(v_id) for v_id in selected_view_ids]
    else:
        views = [uidoc.ActiveView]


    def get_family_name(elem):
        """
        Robustly obtain family name for a family-based element:
        try element type -> FamilyName or Family.Name, fallback to element type name.
        """
        try:
            type_elem = doc.GetElement(elem.GetTypeId())
            # common properties: FamilyName (ElementType) or Family.Name
            if hasattr(type_elem, "FamilyName"):
                name = type_elem.FamilyName
                if name:
                    return name
            if hasattr(type_elem, "Family"):
                fam = getattr(type_elem, "Family")
                if fam is not None and hasattr(fam, "Name"):
                    return fam.Name
            # fallback to type name
            if hasattr(type_elem, "Name"):
                return type_elem.Name
        except Exception:
            pass
        # last resort
        try:
            return elem.Name
        except Exception:
            return ""


    updated = 0
    skipped_no_param = 0
    skipped_readonly = 0

    t = Transaction(doc, "Fill 2D_Rebar_View for DI_ detail items")
    t.Start()
    try:
        for view in views:
            # collect detail components in this view
            elems = FilteredElementCollector(doc, view.Id) \
                .OfCategory(BuiltInCategory.OST_DetailComponents) \
                .WhereElementIsNotElementType() \
                .ToElements()
            for e in elems:
                fam_name = get_family_name(e) or ""
                if fam_name.startswith("DI_"):
                    p = e.LookupParameter("2D_Rebar_View")
                    if p is None:
                        skipped_no_param += 1
                        continue
                    # check writable
                    try:
                        if getattr(p, "IsReadOnly", False):
                            skipped_readonly += 1
                            continue
                    except Exception:
                        # if property not present, attempt set and catch exception
                        pass
                    try:
                        p.Set(view.Name)
                        updated += 1
                    except Exception:
                        # try converting to string set if needed or skip
                        try:
                            p.Set(str(view.Name))
                            updated += 1
                        except Exception:
                            skipped_readonly += 1
        t.Commit()
    except Exception as ex:
        try:
            t.RollBack()
        except Exception:
            pass
        TaskDialog.Show("Fill 2d_Rebar_view", "Failed: {}".format(str(ex)))
    else:
        msg = "Updated: {}\nSkipped (no parameter): {}\nSkipped (read-only/failed): {}".format(
            updated, skipped_no_param, skipped_readonly
        )
        TaskDialog.Show("Fill 2d_Rebar_view", msg)

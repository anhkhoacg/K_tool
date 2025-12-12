"""
Find detail components whose Name begins with "DI_" and contain "Rebar"
but do not contain "_Run line" (case-insensitive) in the selected viewport(s)/view(s)
or the active view, and set their "2D_Rebar_View" parameter to the name of the view they are in.

Usage: run from pyRevit (or adapt the uidoc/doc acquisition for other hosts).
"""

# imports and environment setup
try:
    # pyRevit environment
    from pyrevit import revit, forms
    from pyrevit import script

    DB = revit.db
    uidoc = revit.uidoc
    doc = revit.doc
except Exception:
    # fallback to direct clr/Revit API (common in RevitPythonShell)
    import clr

    clr.AddReference('RevitAPI')
    clr.AddReference('RevitServices')
    from Autodesk.Revit import DB
    from Autodesk.Revit.UI import UIApplication
    from RevitServices.Persistence import DocumentManager

    uidoc = DocumentManager.Instance.CurrentUIDocument
    doc = DocumentManager.Instance.CurrentDBDocument

from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, Viewport, View


def gather_target_views():
    view_set = []
    try:
        sel_ids = uidoc.Selection.GetElementIds()
    except Exception:
        sel_ids = set()

    if sel_ids:
        for elid in sel_ids:
            el = doc.GetElement(elid)
            if el is None:
                continue
            if isinstance(el, View) and not el.IsTemplate:
                view_set.append(el)
            elif isinstance(el, Viewport):
                try:
                    v = doc.GetElement(el.ViewId)
                    if v is not None and not v.IsTemplate:
                        view_set.append(v)
                except Exception:
                    pass
    # fallback to active view if none collected
    if not view_set:
        try:
            active = doc.ActiveView
            if active is not None and not active.IsTemplate:
                view_set.append(active)
        except Exception:
            pass
    # remove duplicates by Id
    unique = {}
    for v in view_set:
        unique[v.Id.IntegerValue] = v
    return list(unique.values())


def set_param_on_details(views):
    from Autodesk.Revit.DB import Transaction, BuiltInCategory, StorageType
    if not views:
        return 0
    total = 0
    t = Transaction(doc, "Set 2D_Rebar_View for DI_* Rebar details")
    t.Start()
    try:
        for v in views:
            coll = FilteredElementCollector(doc, v.Id) \
                .OfCategory(BuiltInCategory.OST_DetailComponents) \
                .WhereElementIsNotElementType()
            for el in coll:
                name = getattr(el, "Name", None) or ""
                # require Name starts with DI_, contains 'Rebar', and does NOT contain '_Run line' (case-insensitive)
                lname = name.lower()
                if not (name.startswith("DI_") and ("Rebar" in name) and
                        ("_run line" not in lname and " run line" not in lname)):
                    continue
                p = el.LookupParameter("2D_Rebar_View")
                if p is None:
                    continue
                # only set string params and writable ones
                try:
                    if p.IsReadOnly:
                        continue
                    # handle different storage types defensively
                    if p.StorageType == StorageType.String:
                        p.Set(v.Name)
                        total += 1
                    else:
                        # try to set textual representation if parameter is other type
                        p.Set(str(v.Name))
                        total += 1
                except Exception:
                    # ignore individual failures
                    continue
    finally:
        t.Commit()
    return total


def main():
    views = gather_target_views()
    count = set_param_on_details(views)
    try:
        # pyRevit-friendly notification
        from pyrevit import forms
        forms.alert("{} detail component parameter(s) updated.".format(count), title="2D_Rebar_View Update")
    except Exception:
        print("{} detail component parameter(s) updated.".format(count))


if __name__ == "__main__":
    main()

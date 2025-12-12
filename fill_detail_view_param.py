"""
Find detail components whose Name begins with "DI_" in the selected view(s) or the active view,
and set their "2D_Rebar_View" parameter to the name of the view they are in.
"""

import clr

# Revit / RevitServices references
clr.AddReference('RevitServices')
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    View,
    Viewport,  # added to support views selected on sheets
)

# Access documents
doc = DocumentManager.Instance.CurrentDBDocument
uiapp = DocumentManager.Instance.CurrentUIApplication
uidoc = uiapp.ActiveUIDocument


def get_views_to_process():
    # If one or more views are selected, use those; also handle viewports on sheets.
    sel_ids = uidoc.Selection.GetElementIds()
    views = []
    if sel_ids:
        for eid in sel_ids:
            el = doc.GetElement(eid)
            if isinstance(el, View):
                if not el.IsTemplate:
                    views.append(el)
            elif isinstance(el, Viewport):
                # get the view hosted by the viewport
                v = doc.GetElement(el.ViewId)
                if isinstance(v, View) and not v.IsTemplate:
                    views.append(v)
    # fallback to active view if none collected
    if not views:
        av = doc.ActiveView
        if av and not av.IsTemplate:
            views = [av]
    return views


def collect_detail_components_in_view(view):
    # Accept a View or a Viewport (or an element id that resolves to one).
    # Resolve to an actual View instance, then collect detail components in that view.
    resolved_view = None
    if isinstance(view, View):
        resolved_view = view
    elif isinstance(view, Viewport):
        resolved_view = doc.GetElement(view.ViewId)
    else:
        # try resolving an ElementId or other reference to an element
        try:
            el = doc.GetElement(view)
            if isinstance(el, View):
                resolved_view = el
            elif isinstance(el, Viewport):
                resolved_view = doc.GetElement(el.ViewId)
        except Exception:
            resolved_view = None

    if not resolved_view:
        return []

    col = FilteredElementCollector(doc, resolved_view.Id) \
        .OfCategory(BuiltInCategory.OST_DetailComponents) \
        .WhereElementIsNotElementType()
    return list(col)


def set_parameter_if_applicable(elem, param_name, value):
    p = elem.LookupParameter(param_name)
    if p and not p.IsReadOnly:
        try:
            p.Set(value)
            return True
        except Exception:
            return False
    return False


def main():
    views = get_views_to_process()
    if not views:
        print("No views to process.")
        return

    updated = 0
    TransactionManager.Instance.EnsureInTransaction(doc)
    try:
        for v in views:
            comps = collect_detail_components_in_view(v)
            for c in comps:
                name = c.Name or ""
                if name.startswith("DI_"):
                    if set_parameter_if_applicable(c, "2D_Rebar_View", v.Name):
                        updated += 1
        TransactionManager.Instance.TransactionTaskDone()
    except Exception as ex:
        # rollback if TransactionManager didn't already close
        try:
            TransactionManager.Instance.ForceCloseTransaction()
        except Exception:
            pass
        raise

    # report
    print("Updated {} detail element(s)".format(updated))


if __name__ == "__main__":
    main()

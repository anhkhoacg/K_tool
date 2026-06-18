__title__ = 'Add filter to current view'
__author__ = 'Khoa le'
__doc__ = """Add filter to current view with the option to search/filter from all filters in the model.
            Noted that the new filter to be set to hide (unstick Visible)  
    Author: Khoa.Le @Haskoning"""

# python
import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import FilteredElementCollector, ParameterFilterElement, ElementId, Transaction
from System.Collections.Generic import List

try:
    from pyrevit import revit, forms

    doc = revit.doc
    uidoc = revit.uidoc


    class FilterItem(forms.TemplateListItem):
        def __init__(self, filt, checked=False):
            # label shown in the list, store the element as item
            # Call base initializer without unsupported keyword and set item explicitly
            forms.TemplateListItem.__init__(self, filt.Name, checked)
            self.item = filt

        @property
        def name(self):
            return "Filter: {}".format(self.item.Name)


    # collect filters into a Python list and sort by Name (case-insensitive)
    filters = list(FilteredElementCollector(doc).OfClass(ParameterFilterElement))
    filters.sort(key=lambda f: (f.Name or "").lower())

    # create TemplateListItem wrappers in sorted order
    ops = [FilterItem(f) for f in filters]

    if not ops:
        forms.alert('No filters found in model.', title='Filters')
    else:
        res = forms.SelectFromList.show(ops, multiselect=True, button_name='Select Filters')
        # res may contain TemplateListItem instances or the underlying items depending on pyrevit version.
        if res:
            # Unwrap selected entries safely: prefer .item if present, otherwise treat entry as the element itself.
            selected_elements = []
            for entry in res:
                if hasattr(entry, 'item'):
                    selected_elements.append(entry.item)
                else:
                    selected_elements.append(entry)

            # Only add filters that are not already applied to the active view
            t = Transaction(doc, "Add Parameter Filters to View")
            try:
                t.Start()
                added_results = []
                added_elements = []
                # snapshot existing filter ids for quick membership checks
                existing_ids = set(doc.ActiveView.GetFilters())
                for e in selected_elements:
                    try:
                        if e.Id in existing_ids:
                            # already present: skip
                            added_results.append((e.Name, False))
                        else:
                            # Revit API AddFilter does not return a reliable success flag in IronPython.
                            doc.ActiveView.AddFilter(e.Id)
                            # Hide newly added filters in the current view.
                            doc.ActiveView.SetFilterVisibility(e.Id, False)
                            added_results.append((e.Name, True))
                            added_elements.append(e)
                            existing_ids.add(e.Id)  # keep snapshot updated
                    except Exception as ex:
                        import traceback

                        print('Failed to add filter "{}" to view: {}'.format(e.Name, ex))
                        traceback.print_exc()
                        raise
                t.Commit()
            except Exception:
                # rollback if transaction started and re-raise
                try:
                    if t.HasStarted:
                        t.RollBack()
                except Exception:
                    pass
                raise

            # select only the filters that were actually added
            if added_elements:
                ids = List[ElementId]([e.Id for e in added_elements])
                try:
                    uidoc.Selection.SetElementIds(ids)
                except Exception as e:
                    import traceback
                    print('Failed to set selection:', e)
                    traceback.print_exc()
                    raise

except Exception:
    # Fallback when pyrevit.forms or revit context is not available (IDE linting / unit tests)
    import traceback

    print('Could not run pyrevit UI. Error:')
    traceback.print_exc()
    # Re-raise the exception so the caller receives it
    raise

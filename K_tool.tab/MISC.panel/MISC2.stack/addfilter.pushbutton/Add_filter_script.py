__title__ = 'Add filter to current view'
__author__ = 'Khoa le'
__doc__ = """Add filter to current view
    Author: Khoa.Le @Haskoning"""

# python
import clr

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import FilteredElementCollector, ParameterFilterElement, ElementId, Transaction
from System.Collections.Generic import List

try:
    from pyrevit import revit, forms

    doc = revit.doc


    class FilterItem(forms.TemplateListItem):
        def __init__(self, filt, checked=False):
            # label shown in the list, store the element as item
            # Call base initializer without unsupported keyword and set item explicitly
            forms.TemplateListItem.__init__(self, filt.Name, checked)
            self.item = filt

        @property
        def name(self):
            return "Filter: {}".format(self.item.Name)


    filters = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
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

            # Add each selected filter to the current (active) view inside a Transaction
            t = Transaction(doc, "Add Parameter Filters to View")
            try:
                t.Start()
                added_results = []
                for e in selected_elements:
                    try:
                        added_flag = doc.ActiveView.AddFilter(e.Id)
                        added_results.append((e.Name, bool(added_flag)))
                    except Exception as ex:
                        # report and re-raise so caller sees the failure
                        import traceback

                        print
                        'Failed to add filter "{}" to view: {}'.format(e.Name, ex)
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

            # set Revit UI selection to the chosen filters (do this after adding them)
            ids = List[ElementId]([e.Id for e in selected_elements])
            try:
                revit.uidoc.Selection.SetElementIds(ids)
            except Exception as e:
                # Report and re-raise so caller can handle the failure
                import traceback

                print
                'Failed to set selection:', e
                traceback.print_exc()
                raise

            # feedback which filters were added and whether AddFilter returned True
            print
            'Selected filters and add results:', added_results
except Exception:
    # Fallback when pyrevit.forms or revit context is not available (IDE linting / unit tests)
    import traceback

    print
    'Could not run pyrevit UI. Error:'
    traceback.print_exc()
    # Re-raise the exception so the caller receives it
    raise

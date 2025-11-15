__title__ = 'Set Workset Visibility'
__author__ = 'Khoa le'
__doc__ = """Set Workset Visibility
    Author: Khoa.Le @Haskoning"""

# python
import clr

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import FilteredWorksetCollector, WorksetKind, Workset
from Autodesk.Revit.DB import Transaction, WorksetVisibility

try:
    from pyrevit import revit, forms

    doc = revit.doc


    class WorksetItem(forms.TemplateListItem):
        def __init__(self, ws, checked=False):
            # label shown in the list, store the workset as item
            forms.TemplateListItem.__init__(self, ws.Name, checked)
            self.item = ws

        @property
        def name(self):
            return "Workset: {}".format(self.item.Name)


    # Collect user-created worksets
    workset_collector = FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)
    ops = [WorksetItem(w) for w in workset_collector]

    if not ops:
        forms.alert('No user-created worksets found in the model.', title='Worksets')
    else:
        res = forms.SelectFromList.show(ops, multiselect=True, button_name='Select Worksets')
        if res:
            # Unwrap selected entries safely: prefer .item if present, otherwise treat entry as the workset itself.
            selected_worksets = []
            for entry in res:
                if hasattr(entry, 'item'):
                    selected_worksets.append(entry.item)
                else:
                    selected_worksets.append(entry)

            # Provide feedback: list selected workset names
            names = [ws.Name for ws in selected_worksets]
            msg = "Selected worksets:\n" + "\n".join(names)
            forms.alert(msg, title='Selected Worksets')
            print
            'Selected worksets:', names

            # Now: hide the selected worksets in the active view inside a Transaction
            try:
                # determine target view: prefer pyrevit.revit.active_view, fallback to document ActiveView
                try:
                    target_view = revit.active_view
                except Exception:
                    target_view = doc.ActiveView

                trans = Transaction(doc, "Hide selected worksets")
                trans.Start()
                for ws in selected_worksets:
                    try:
                        # set workset visibility to Hidden for this view
                        target_view.SetWorksetVisibility(ws.Id, WorksetVisibility.Hidden)
                    except Exception:
                        # continue to attempt others; will rollback if outer exception occurs
                        pass
                trans.Commit()
                forms.alert("Selected worksets have been set to Hidden in the active view.", title="Worksets Hidden")
            except Exception:
                try:
                    trans.RollBack()
                except Exception:
                    pass
                forms.alert("Failed to hide selected worksets. See console for details.", title="Error")

except Exception:
    # Fallback when pyrevit.forms or revit context is not available (IDE linting / unit tests)
    import traceback

    print
    'Could not run pyrevit UI. Error:'
    traceback.print_exc()
    # Re-raise the exception so the caller receives it
    raise

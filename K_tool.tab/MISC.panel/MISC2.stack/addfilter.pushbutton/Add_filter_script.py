__title__ = 'Add filter to current view'
__author__ = 'Khoa le'
__doc__ = """Add filters (rule-based and selection filters) to the current view, other views or view templates,
            with the option to search/filter from all filters in the model.
            Choose how the added filters display: Hide (untick Visible, default), Show, Halftone or Colour override.
            Filters already in the current view are marked [in view].
            "Edit / New Filter" button in the list opens the Revit Filters dialog.
            Shift+Click: open the Revit Filters dialog directly.
    Author: Khoa.Le @Haskoning"""

# python
import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import (FilteredElementCollector, FilterElement, SelectionFilterElement,
                               FillPatternElement, OverrideGraphicSettings, Color,
                               BuiltInParameter, ElementId)
from Autodesk.Revit.UI import RevitCommandId, PostableCommand

from pyrevit import revit, forms, script, EXEC_PARAMS
from pyrevit.compat import get_elementid_value_func

id_val = get_elementid_value_func()  # ElementId -> int (IntegerValue / Value by Revit version)

doc = revit.doc
uidoc = revit.uidoc

EDIT_BUTTON_LABEL = 'Edit / New Filter'

MODE_HIDE = 'Hide'
MODE_SHOW = 'Show'
MODE_HALFTONE = 'Halftone'
MODE_COLOUR = 'Colour override...'

SW_VIEWS = 'Apply to other views (pick)'
SW_TEMPLATES = 'Apply to view templates (pick)'


# --------------------------------------------------------------------------- helpers
def open_filters_dialog():
    """Open Revit's built-in Filters dialog (create / edit / rename / delete filters).
    PostCommand runs after this script ends."""
    cmd_id = RevitCommandId.LookupPostableCommandId(PostableCommand.Filters)
    revit.HOST_APP.uiapp.PostCommand(cmd_id)


def supports_filters(view):
    """Sheets, schedules, legends etc. cannot take V/G filters."""
    try:
        return view is not None and view.AreGraphicsOverridesAllowed()
    except Exception:
        return False


def controlling_template(view):
    """Return the view template that controls V/G Filters for this view, or None."""
    if view.IsTemplate or view.ViewTemplateId == ElementId.InvalidElementId:
        return None
    template = doc.GetElement(view.ViewTemplateId)
    if template is None:
        return None
    filters_param = ElementId(BuiltInParameter.VIS_GRAPHICS_FILTERS)
    non_controlled = set(id_val(p) for p in template.GetNonControlledTemplateParameterIds())
    if id_val(filters_param) in non_controlled:
        return None
    return template


def get_solid_fill_id():
    for fp in FilteredElementCollector(doc).OfClass(FillPatternElement):
        try:
            if fp.GetFillPattern().IsSolidFill:
                return fp.Id
        except Exception:
            pass
    return None


def hex_to_color(argb_hex):
    """'#AARRGGBB' (from forms.ask_for_color) -> Revit Color."""
    h = argb_hex.replace('#', '')
    return Color(int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))


def build_overrides(mode, colour):
    ogs = OverrideGraphicSettings()
    if mode == MODE_HALFTONE:
        ogs.SetHalftone(True)
    elif mode == MODE_COLOUR and colour is not None:
        solid_id = get_solid_fill_id()
        ogs.SetProjectionLineColor(colour)
        ogs.SetCutLineColor(colour)
        if solid_id is not None:
            ogs.SetSurfaceForegroundPatternId(solid_id)
            ogs.SetSurfaceForegroundPatternColor(colour)
            ogs.SetCutForegroundPatternId(solid_id)
            ogs.SetCutForegroundPatternColor(colour)
    return ogs


# --------------------------------------------------------------------------- UI classes
class FilterItem(forms.TemplateListItem):
    def __init__(self, filt, in_view=False):
        forms.TemplateListItem.__init__(self, filt, False)
        self.in_view = in_view

    @property
    def name(self):
        kind = '[Selection]' if isinstance(self.item, SelectionFilterElement) else '[Rule]'
        suffix = '   [in view]' if self.in_view else ''
        return '{} {}{}'.format(kind, self.item.Name, suffix)


class FilterSelectFromList(forms.SelectFromList):
    """SelectFromList where the 'Toggle All' button is replaced by 'Edit / New Filter'."""
    edit_requested = False

    def _setup(self, **kwargs):
        forms.SelectFromList._setup(self, **kwargs)
        self.toggleall_b.Content = EDIT_BUTTON_LABEL
        self.toggleall_b.ToolTip = 'Close this list and open the Revit Filters dialog'

    def _list_options(self, option_filter=None):
        # base class resets the button text on every search change
        forms.SelectFromList._list_options(self, option_filter)
        self.toggleall_b.Content = EDIT_BUTTON_LABEL

    def toggle_all(self, sender, args):  # bound to the Toggle button in XAML
        self.edit_requested = True
        self.response = None
        self.Close()


# --------------------------------------------------------------------------- main
# Shift+Click goes straight to the Filters dialog
if EXEC_PARAMS.config_mode:
    open_filters_dialog()
    script.exit()

active_view = doc.ActiveView
current_ids = set()
if supports_filters(active_view):
    current_ids = set(id_val(i) for i in active_view.GetFilters())

# 1) pick filters (rule-based + selection filters)
filters = list(FilteredElementCollector(doc).OfClass(FilterElement))
filters.sort(key=lambda f: (f.Name or '').lower())

if not filters:
    if forms.alert('No filters found in model.\nOpen the Filters dialog to create one?',
                   title='Filters', yes=True, no=True):
        open_filters_dialog()
    script.exit()

ops = [FilterItem(f, id_val(f.Id) in current_ids) for f in filters]
dlg = FilterSelectFromList(ops, 'Add Filters to View',
                           forms.DEFAULT_INPUTWINDOW_WIDTH, forms.DEFAULT_INPUTWINDOW_HEIGHT,
                           multiselect=True, button_name='Select Filters')
dlg.ShowDialog()
if dlg.edit_requested:
    open_filters_dialog()
    script.exit()
selected_filters = dlg.response
if not selected_filters:
    script.exit()

# 2) display mode + target switches
res = forms.CommandSwitchWindow.show(
    [MODE_HIDE, MODE_SHOW, MODE_HALFTONE, MODE_COLOUR],
    switches=[SW_VIEWS, SW_TEMPLATES],
    message='How should the added filters display?')
mode, switches = res if res else (None, {})
if not mode:
    script.exit()

colour = None
if mode == MODE_COLOUR:
    picked = forms.ask_for_color()
    if not picked:
        script.exit()
    colour = hex_to_color(picked)

# 3) resolve target views
targets = []
skipped_views = []  # (view name, reason)

if switches.get(SW_VIEWS) or switches.get(SW_TEMPLATES):
    if switches.get(SW_VIEWS):
        picked_views = forms.select_views(title='Select Views', multiple=True, doc=doc,
                                          filterfunc=supports_filters) or []
        targets.extend(picked_views)
    if switches.get(SW_TEMPLATES):
        picked_templates = forms.select_viewtemplates(title='Select View Templates', multiple=True,
                                                      doc=doc, filterfunc=supports_filters) or []
        targets.extend(picked_templates)
else:
    if not supports_filters(active_view):
        forms.alert('The active view "{}" does not support filters '
                    '(sheets, schedules, legends...).'.format(active_view.Name),
                    title='Filters')
        script.exit()
    template = controlling_template(active_view)
    if template is not None:
        if forms.alert('Filters of view "{}" are controlled by view template "{}".\n\n'
                       'Add the filters to the template instead?\n'
                       '(affects every view using this template)'.format(active_view.Name, template.Name),
                       title='View Template', yes=True, no=True):
            targets.append(template)
        else:
            script.exit()
    else:
        targets.append(active_view)

# picked views can also be controlled by a template -> skip with a reason
final_targets = []
seen = set()
for v in targets:
    if id_val(v.Id) in seen:
        continue
    seen.add(id_val(v.Id))
    tpl = controlling_template(v)
    if tpl is not None:
        skipped_views.append((v.Name, 'filters controlled by template "{}"'.format(tpl.Name)))
    else:
        final_targets.append(v)

if not final_targets:
    msg = 'No views to update.'
    if skipped_views:
        msg += '\n\n' + '\n'.join('- {}: {}'.format(n, r) for n, r in skipped_views)
    forms.alert(msg, title='Filters')
    script.exit()

# 4) apply
ogs = build_overrides(mode, colour)
added, already, failed = [], [], []  # (view name, filter name[, error])

with revit.Transaction('Add Filters to View'):
    for view in final_targets:
        existing = set(id_val(i) for i in view.GetFilters())
        for f in selected_filters:
            if id_val(f.Id) in existing:
                already.append((view.Name, f.Name))
                continue
            try:
                view.AddFilter(f.Id)
                view.SetFilterVisibility(f.Id, mode != MODE_HIDE)
                if mode in (MODE_HALFTONE, MODE_COLOUR):
                    view.SetFilterOverrides(f.Id, ogs)
                added.append((view.Name, f.Name))
            except Exception as ex:
                failed.append((view.Name, f.Name, str(ex)))

# 5) summary
lines = ['Mode: {}'.format(mode.rstrip('.')),
         'Added: {}   |   Already in view: {}   |   Failed: {}'.format(len(added), len(already), len(failed))]
if len(final_targets) == 1:
    lines.append('View: {}'.format(final_targets[0].Name))
else:
    lines.append('Views: {}'.format(len(final_targets)))
if already:
    lines.append('\nSkipped (already in view):')
    lines.extend('- {} > {}'.format(v, f) for v, f in already[:15])
    if len(already) > 15:
        lines.append('  ... and {} more'.format(len(already) - 15))
if skipped_views:
    lines.append('\nSkipped views:')
    lines.extend('- {}: {}'.format(n, r) for n, r in skipped_views)
if failed:
    lines.append('\nFailed:')
    lines.extend('- {} > {}: {}'.format(v, f, e) for v, f, e in failed[:15])

forms.alert('\n'.join(lines), title='Add Filters', warn_icon=bool(failed))

# -*- coding: utf-8 -*-
"""Shift+Click: choose what Auto Dim dimensions and the paper offsets."""
from pyrevit import forms, script

# (config key, label, default). Keep keys/defaults in sync with script.py.
OPTIONS = [
    ("h_chain", "Horizontal - chain", True),
    ("h_overall", "Horizontal - overall", True),
    ("v_chain", "Vertical - chain", True),
    ("v_overall", "Vertical - overall", True),
    ("h_top", "Place horizontal dims ABOVE (default below)", False),
    ("v_right", "Place vertical dims on the RIGHT (default left)", False),
    ("ref_planes", "Use family reference planes as references", True),
    ("planes_only", "Reference planes only (ignore faces)", False),
    ("no_weak", "Ignore Weak Reference planes", True),
]
FIRST_DEFAULT = 8.0
SPACING_DEFAULT = 7.0


def as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


cfg = script.get_config()

items = [forms.TemplateListItem(label,
                                checked=as_bool(cfg.get_option(key, default)))
         for key, label, default in OPTIONS]
chosen = forms.SelectFromList.show(
    items,
    title="Auto Dim - Settings",
    multiselect=True,
    button_name="Next")
if chosen is None:
    script.exit()
chosen = set(chosen)

text = forms.ask_for_string(
    default="{}, {}".format(cfg.get_option("first_paper_mm", FIRST_DEFAULT),
                            cfg.get_option("spacing_paper_mm",
                                           SPACING_DEFAULT)),
    prompt="Paper offsets in mm: element -> first line, line spacing",
    title="Auto Dim - Settings")
if text is None:
    script.exit()
try:
    first, spacing = [float(t) for t in text.split(",")]
    if first < 0 or spacing <= 0:
        raise ValueError
except ValueError:
    forms.alert("Enter two numbers, e.g. 8, 7", exitscript=True)

for key, label, _default in OPTIONS:
    setattr(cfg, key, label in chosen)
cfg.first_paper_mm = first
cfg.spacing_paper_mm = spacing
script.save_config()

forms.alert("Auto Dim settings saved.")

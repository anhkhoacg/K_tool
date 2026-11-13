# -*- coding: utf-8 -*-
"""Shift+Click: set the max distance from an element to its nearest grid."""
from pyrevit import forms, script

cfg = script.get_config()
current = cfg.get_option("tolerance_mm", 1500)

val = forms.ask_for_string(
    default=str(current),
    prompt="Max distance from element to nearest grid (mm).\n"
           "Elements further away are marked OFF-GRID.\n"
           "Enter 0 to disable the check.",
    title="Grid Mark - Settings")

if val is not None:
    try:
        tol = float(val)
        if tol < 0:
            raise ValueError
        cfg.tolerance_mm = tol
        script.save_config()
        forms.alert("Tolerance set to {} mm".format(tol))
    except ValueError:
        forms.alert("Please enter a number >= 0.", exitscript=True)

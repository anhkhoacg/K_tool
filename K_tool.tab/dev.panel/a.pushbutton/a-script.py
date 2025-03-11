from pyrevit import forms
layout = '<Window ' \
         'xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" ' \
         'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" ' \
         'ShowInTaskbar="False" ResizeMode="NoResize" ' \
         'WindowStartupLocation="CenterScreen" ' \
         'HorizontalContentAlignment="Center">' \
         '</Window>'
w = forms.WPFWindow(layout, literal_string=True)
w.show()
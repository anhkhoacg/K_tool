# K_tool
 Revit tool 
K_tool
What is this?
K_tool is/will be a toolbar for the use with pyRevit built by Le Anh Khoa (anhkhoacg@gmail.com). 


Who is it for?
Khoa uses the tool for his daily works and also to learn RevitAPI. It is free to use/take but no warranty that it would work.


Directly Installing K_tool

The following method can be used to avoid installing pyRevit via the Settings menu from within Revit itself, and might be beneficial to automate company related installation process' as well. 
Thanks to Jean-Marc Couffin for suggesting/helping write this section!

1.Install pyRevit from https://github.com/eirannejad/pyRevit/releases

2.WIN+R, then type 'cmd'

3.In the command line, install the extension with the following command 
--

pyrevit extend ui K_tool https://github.com/anhkhoacg/K_tool --dest="C:\thePathWhereYouWantItInstalled" --branch=main

--

If Revit was opened, use the reload button of pyRevit

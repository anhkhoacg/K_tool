# K_tool
 Revit tool 
K_tool
What is this?
K_tool is/will be a toolbar for the use with pyRevit built by Le Anh Khoa (anhkhoacg@gmail.com). 
Having used and taught Dynamo for many years now, he's come to see pyRevit as a natural 'next step' for users looking to package up more efficient, stable and scalable tools to organisations.

Who is it for?
These tools will generally be aimed towards architects looking to get more out of Revit and/or learn more about pyRevit. Expect tools to typically focus on efficiency gains usually made in the mid to late stages of project delivery (as well as some purely miscellaneous tools).

Read more at the wiki here: https://github.com/anhkhoacg/K_tool

Directly Installing K_tool
The following method can be used to avoid installing pyRevit via the Settings menu from within Revit itself, and might be beneficial to automate company related installation process' as well. Thanks to Jean-Marc Couffin for suggesting/helping write this section!

1.Install pyRevit from https://github.com/eirannejad/pyRevit/releases
2.WIN+R, then type 'cmd'
3.In the command line, install the extension with the following command 
--
pyrevit extend ui K_tool https://github.com/anhkhoacg/K_tool --dest="C:\thePathWhereYouWantItInstalled" --branch=main
--
If Revit was opened, use the reload button of pyRevit
Manually installing K_tool
If you want to quickly set up K_tool yourself, you can simply add it to your Roaming folder like below (reach this by typing %appdata% into the explorer address bar), and copy the contents of this git to that folder instead of using the CLI method above. For basic users this is generally the recommended approach:

K_tool path
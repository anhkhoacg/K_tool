# K_tools / Công cụ của K

## English
Tiếng Việt bên dưới
### About
K_tool is a Revit toolbar extension for pyRevit developed by Le Anh Khoa (anhkhoacg@gmail.com) to optimize his daily
Revit workflows.

This is a personal learning project for Revit API and is provided free to use with no warranties.

### Installation

#### Prerequisites
- pyRevit (install from [pyRevit releases](https://github.com/eirannejad/pyRevit/releases))

#### Installation Steps
1. Open Command Prompt (WIN+R, type 'cmd')
2. Run the following command:
      ```
      pyrevit extend ui K_tool https://github.com/anhkhoacg/K_tool --dest="C:\YourInstallPath" --branch=main
      ```
      Note: Replace `C:\YourInstallPath` with your desired installation directory
3. Restart Revit or use pyRevit's reload button if Revit is already open

### Features
#### 1.  Worksets Panel
  - **Hide Worksets** : Hide Workset of selected elements in the view
  - **Show Workset**  : Set the current workset to **Show**
  - **Show all Worksets** : Set all worksets in models to **Show**
  - **Set Workset Visibility** : Set Hide/Show Worksets with `User Interface` to selected and search/filter
#### 2. Rebar Panel
  - **Obscure** : set all rebar in view to Obscure (underneat of others elements)
  - **Unobscure** : set all rebar in view to Unobscure ( on top of other elements)
  - **ShowAllRebar_py** : Display all rebar in rebar set for all rebar in view
  - **CopyRebarNumberToScheduleMark** : Copy RebarNumber To ScheduleMark

  - **MultiRebarAnnotation** : Add bulk MultiRebarAnnotation 
  - **Renumber** : To renunber the rebar of partitions
####  3. Miscelanous
  -**Open in Autodesk Docs**: This script will open the current Revit project in Autodesk Docs in your default web browser.
  -**Dimension Grids** :Select grid lines to automatically create dimensions between them and overall line.
  - **Flip Grids** : to Flip Grids buble
  - **Grid 3D to 2D** :  Convert selected Revit Grids from 3D (Model) to 2D (ViewSpecific) in the active view.
  - **Add filter to current view'** : Add filter to current view with the option to search/filter from all filters in the model.
  - **change Background** : change Background :D 

### License
Free to use with no warranties :P

## Tiếng Việt
### Giới thiệu
Công cụ của K là tiện ích mở rộng thanh công cụ cho pyRevit, được phát triển bởi Lê Anh Khoa (anhkhoacg@gmail.com) để tối ưu hóa quy trình làm việc với Revit hàng ngày.

Đây là dự án học tập cá nhân về Revit API và được cung cấp miễn phí không kèm bảo hành.

### Cài đặt
#### Yêu cầu
- pyRevit (cài đặt từ [pyRevit releases](https://github.com/eirannejad/pyRevit/releases))
#### Các bước cài đặt
1. Mở Command Prompt (WIN+R, gõ 'cmd')
2. Chạy lệnh sau:
   ```
   pyrevit extend ui K_tool https://github.com/anhkhoacg/K_tool --dest="C:\thu_muc_cai_đat" --branch=main
   ```
   Lưu ý: Thay `"C:\thu_muc_cai_đat"` bằng thư mục bạn muốn
3. Khởi động lại Revit hoặc dùng nút reload của pyRevit nếu Revit đang mở

### Tính năng
### 1. Worksets Panel
- **Hide Worksets** : Ẩn workset của phần tử được chọn
- **Show Workset** : Hiển thị workset hiện tại
- **Show all Worksets** :Hiển thị tất cả workset
- **Set Workset Visibility**: Thiết lập hiển thị với bộ lọc ( filter) với tính năng tìm kiếm (search/ filter)
### 2. Rebar Panel
- **Obscure** : Thép nằm dưới phần tử khác
- **Unobscure** : Thép hiển thị phía trên
- **ShowAllRebar_py**Hiển thị toàn bộ rebar
- **CopyRebarNumberToScheduleMark** : Copy số rebar sang schedule mark
- **MultiRebarAnnotation** : Gắn annotation hàng loạt
- **Renumber** :  Đánh lại số rebar

### 3. Miscellaneous
- **Open in Autodesk Docs** : Mở model trên Autodesk Docs
- **Dimension Grids** : Tạo dim grid tự động
- **Flip Grids** : Đảo bubble grid
- **Grid 3D to 2D** : Chuyển grid 3D sang 2D 
- **Add filter to current view** : Thêm filter vào view với tính năng search/filter.
- **Change Background** :Thay đổi màu nền ( Trắng-đen-Xám)

### Giấy phép
Miễn phí sử dụng không kèm bảo hành :D

---


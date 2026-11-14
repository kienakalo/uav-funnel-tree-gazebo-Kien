# Dữ liệu

Thư mục này chứa cả dữ liệu của bên thứ ba và dữ liệu do nhóm tạo. Hướng dẫn
chạy nằm trong [README chính](../README.md); nguồn và giấy phép chi tiết ở
[ATTRIBUTION.md](../ATTRIBUTION.md).

## Ba thư mục con

| Thư mục | Nội dung | Nguồn | Giấy phép |
| --- | --- | --- | --- |
| `source/` | `city.glb`, mô hình thành phố 20 MB | Saigon 3D City | CC BY 4.0 |
| `input/` | Năm mesh `.geom` cho kiểm thử hồi quy | Nhóm tác giả | BSD-3-Clause |
| `expected/` | Đường đi tham chiếu cho từng mesh | Nhóm tác giả | BSD-3-Clause |

`source/city.glb` là **input của pipeline**, không phải asset trình diễn:
`prepare.py`, `prepare_urban.py` và các công cụ dựng miền bay đọc trực tiếp
file này. Không sửa file gốc; mọi dẫn xuất nằm trong `generated/`.

Một bản `city.glb` đặt ở `data/input/` sẽ bị `.gitignore` bỏ qua để tránh
chép trùng mô hình; đường dẫn chuẩn duy nhất là `data/source/city.glb`.

## Định dạng `.geom`

`data/input/*.geom` là lưới tam giác dạng văn bản:

- Dòng đầu: `V F E` — số đỉnh, số mặt, số cạnh khai báo.
- `V` dòng tiếp theo: `x y z`.
- `F` dòng tiếp theo: `3 a b c` — một tam giác, chỉ số đỉnh bắt đầu từ 0.

`src/mesh.py` chỉ nhận mặt tam giác. Giá trị `E` **không được dùng**: vài file
mẫu khai báo sai, nên số cạnh thực được suy ra từ danh sách mặt.

`data/expected/*.geom` lưu đường đi tham chiếu, mỗi dòng một đường:

```text
k [x y z] [x y z] ...
```

`k` là số điểm và phải `>= 2`. Dấu ngoặc vuông được bỏ khi đọc, nên định dạng
này khớp với file `plan.py` xuất ra trong `generated/`.

## Năm mesh mẫu

| Mesh | Kích thước | Dùng ở |
| --- | --- | --- |
| `cliff` | 7 đỉnh, 10 mặt | `check.py`, `plan.py` (mặc định), `tests/test_funnel_target_scope.py` |
| `demo_mesh` | 31 đỉnh, 62 mặt | `check.py` |
| `J17` | 10 đỉnh, 16 mặt | `check.py` |
| `L` | 12 đỉnh, 20 mặt | `check.py`, `tests/test_funnel_target_scope.py` |
| `star` | 16 đỉnh, 28 mặt | `check.py` (nguồn 0 và 1), `tests/test_funnel_target_scope.py` |

`check.py` đối chiếu chiều dài đường đi với `expected/`, trừ cặp `star` nguồn
1 vì không có dữ liệu tham chiếu cho trường hợp đó.

## Quy tắc sửa dữ liệu

- Các file `.geom` được đối xử **byte-exact**: `.gitattributes` đặt
  `*.geom -text` để Git không đổi kiểu xuống dòng. Đừng chạy formatter trên
  chúng.
- `check.py` so sánh chiều dài với dung sai dựa trên việc làm tròn 4 chữ số
  thập phân trong `expected/`. Sửa toạ độ phải cập nhật cả `input/` lẫn
  `expected/`, hoặc chấp nhận kiểm thử thất bại.
- Muốn thêm mesh: thêm `input/<tên>.geom`, `expected/<tên>.geom`, rồi khai
  báo cặp `(tên, nguồn)` trong `check.py`.

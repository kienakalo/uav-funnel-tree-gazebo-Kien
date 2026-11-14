# Mã nguồn

Tám module dùng chung. Đây **không phải package**: không có `__init__.py`,
các module được import trực tiếp theo tên (`from mesh import ...`) sau khi
chương trình thêm `src/` vào `sys.path`. Mọi script trong repo đều làm việc
này; script mới cần thêm cùng một dòng.

## Vai trò và phụ thuộc

| Module | Vai trò | Import nội bộ |
| --- | --- | --- |
| `mesh.py` | `Point`, `Mesh`, `read_geom`: dữ liệu bề mặt, quan hệ kề, góc và khoảng cách | — |
| `funnel_tree.py` | Lan truyền Funnel, `clip_children`, `reconstruct`, `solve`, `propagate` | — (dùng giao diện `Mesh`, không import) |
| `verification.py` | `read_mesh`, `read_paths`, `path_length`, `edge_distances`, `segment_on_mesh` | — (chỉ stdlib) |
| `city.py` | `load_city`, `write_stl`: đọc GLB, bake transform, xuất lưới và STL | — (NumPy) |
| `trajectory.py` | `Trajectory`, `control_acceleration`: tham số hoá thời gian trên polyline | — |
| `urban_navigation.py` | `obstacle_grid`, `intersects_boxes`, `plan_urban`: cột vật cản → hành lang lưới → Funnel | `mesh`, `funnel_tree`, `verification` |
| `drone_system.py` | `DroneSystem`: plugin Gazebo, mô hình chất điểm 1 kg và telemetry | `trajectory`, `gz.sim8` |
| `funnel_drone_system.py` | Plugin bám tuyến Funnel, kế thừa `DroneSystem` | `drone_system` |

Thứ tự đọc gợi ý: `mesh` → `funnel_tree` → `verification`, rồi `city` và
`trajectory`, sau cùng hai plugin Gazebo.

`funnel_tree.py` không import `mesh`; nó chỉ gọi các thuộc tính và phương thức
mà `Mesh` cung cấp. Đổi tên hoặc bỏ một thuộc tính của `Mesh` sẽ làm hỏng
module này dù không có lỗi import.

## Hai môi trường chạy

`src/drone_system.py` và `src/funnel_drone_system.py` chạy **bên trong Gazebo**,
dùng Python hệ thống và binding `gz.sim8`, không dùng `.venv`. Vì vậy hai
module này chỉ nên dùng thư viện chuẩn; thư viện phân tích (NumPy, Shapely,
Matplotlib) phải nằm ở phần lập kế hoạch, không đặt trong plugin.

Các module còn lại chạy bằng `.venv/bin/python` khi có, hoặc `python3` của hệ
thống.

## Bất biến: chữ ký phụ thuộc mã nguồn

Nhiều kết quả trong `generated/` ghi SHA256 của mã nguồn. Sửa mã sẽ làm chữ
ký thay đổi và các bước sau từ chối chạy cho tới khi tính lại:

| Nơi ghi chữ ký | File mã nguồn được băm |
| --- | --- |
| `tools/run_funnel_benchmark.py` | `funnel_tree.py`, `mesh.py`, `verification.py` |
| `tools/run_city_three_goals.py` | `funnel_tree.py` |
| `tools/plan_surface_delivery.py` | `funnel_tree.py`, `mesh.py` |
| `generated/source_header_audit.json` | Toàn bộ 66 file `.py` và `.sh` |

`tools/prepare_funnel_physics.py` kiểm tra lại chữ ký benchmark trước khi
dựng world, nên nếu sửa `funnel_tree.py` mà không chạy lại benchmark, lệnh mô
phỏng sẽ dừng với thông báo "Benchmark inputs or code changed".

Sau khi sửa mã:

```bash
.venv/bin/python check.py
.venv/bin/python tools/verify_project_results.py
```

Nếu `verify_project_results.py` báo lệch, chạy lại đúng công cụ ở bảng trên
rồi kiểm tra lại. Chỉ cập nhật tay dấu vân tay khi thay đổi thuần tuý chú
thích, như đợt đổi tên chủ sở hữu bản quyền.

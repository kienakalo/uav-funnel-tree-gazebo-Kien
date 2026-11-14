# Script chạy

Tất cả script `cd` về thư mục gốc repository và chạy trên Ubuntu/WSL. Không
dùng PowerShell. Hướng dẫn từng bước của demo hiện tại nằm trong
[RUNBOOK_CURRENT.md](../RUNBOOK_CURRENT.md).

## Bảng script

| Script | Dùng khi | Ghi chú |
| --- | --- | --- |
| `install_ubuntu.sh` | Cài máy mới | Chỉ Ubuntu 24.04; cài `gz-harmonic`, `python3-gz-sim8`, `python3-numpy` bằng apt |
| `gazebo_system_python.sh` | Nội bộ | Chạy `gz` bằng Python hệ thống, tách khỏi `.venv` |
| `run.sh [pose\|physics]` | Demo cũ `hcm_demo.sdf` | `pose` phát animation; `physics` ghi `generated/physics_telemetry.csv` |
| `run_funnel.sh` | Xem trước tuyến đã kiểm chứng | Gửi `set_pose`, không điều khiển vật lý |
| `run_funnel_physics.sh [case]` | Demo bám tuyến hiện tại | Dựng world, chạy plugin điều khiển lực |
| `run_surface_gpu.sh` | Ca `surface_delivery` trên WSLg | Bọc `run_funnel_physics.sh` với `GALLIUM_DRIVER=d3d12` |
| `run_surface_cpu.sh` | Ca `surface_delivery` không có GPU | Bọc với `LIBGL_ALWAYS_SOFTWARE=1` và `llvmpipe` |
| `run_urban.sh` | Nhiệm vụ đô thị thấp | Gọi `prepare_urban.py`, mở `hcm_demo.sdf` |

## `run_funnel_physics.sh`

Các ca: `original` (mặc định), `cross_city`, `short_open`, `narrow_corridor`,
`low_collision`, `delivery`, `surface_delivery`.

Tuỳ chọn:

- `--show-surface`: hiện lưới 3D và cạnh tam giác.
- `--destination=g1\|g2\|g3`: chỉ dùng với `surface_delivery`; đọc kế hoạch đã
  lưu trong `generated/city_three_goals/`.
- `--software`: ép software rendering.

Thư mục đầu ra:

| Ca | Thư mục |
| --- | --- |
| `original` | `generated/funnel_physics/` |
| Các ca khác | `generated/funnel_physics/<ca>/` |
| Có `--destination` | `generated/city_three_goals/<g>/` |

## Hai môi trường Python

- **Lập kế hoạch và phân tích:** `.venv/bin/python` nếu tồn tại, ngược lại
  `python3`. Cần các gói trong `requirements-demo.txt`.
- **Plugin Gazebo:** Python hệ thống qua `/usr/bin/gz`. `gazebo_system_python.sh`
  bỏ `VIRTUAL_ENV` và `PYTHONHOME`, rồi đặt `PYTHONPATH` gồm `src/` và
  `/usr/lib/python3/dist-packages`. Đây là lý do plugin không thấy thư viện
  trong `.venv`.

`run.sh`, `run_funnel.sh` và `run_urban.sh` gọi `python3` trực tiếp để dựng
world; chúng cần `python3-numpy` của apt.

## Thứ tự chạy

```bash
bash scripts/install_ubuntu.sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
bash scripts/run_surface_gpu.sh
```

`run_funnel_physics.sh` **không tái tạo** kế hoạch. Nó đọc các artifact đã
kiểm tra trong `generated/` và dừng nếu SHA256 không khớp. Sau khi sửa mã
nguồn, chạy lại pipeline tương ứng (xem [src/README.md](../src/README.md))
trước khi mở mô phỏng.

## Cảnh báo

- Chỉ mở một phiên Gazebo cho mỗi world; script kiểm tra service trùng tên và
  thoát nếu world đang chạy.
- Telemetry cũ được sao lưu thành `physics_telemetry_<timestamp>.csv` trước
  mỗi lần chạy.
- `run_surface_gpu.sh` từ chối `--software`; hai chế độ loại trừ nhau.
- Lần chạy đầu có thể mất vài giây chờ plugin khởi tạo; script chờ tối đa 20
  giây rồi dừng kèm hướng dẫn đọc `gazebo_gui.log`.

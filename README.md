# UAV giao hàng trên bề mặt 3D bằng Funnel Tree

Trong dự án này, nhóm triển khai thuật toán Funnel Tree bằng Python để lập
tuyến trên bề mặt đa diện và mô phỏng một UAV bám tuyến trong Gazebo Harmonic.
Quy trình đọc mô hình thành phố `city.glb`,
dựng bề mặt dẫn đường 3D phía trên địa hình và công trình, chạy Funnel Tree,
đối chiếu độ dài với bộ giải MMP độc lập, rồi mô phỏng tiếp cận điểm giao hàng.

![Bản đồ và tuyến bay](generated/funnel_physics/surface_delivery/city_overview.png)

## Kết quả hiện tại

| Thành phần | Kết quả đã kiểm tra |
| --- | --- |
| Mô hình thành phố | 301.490 tam giác, đổi trục và chuẩn hóa kích thước ngang về 200 đơn vị |
| Bề mặt dẫn đường 3D | 858 đỉnh, 1.600 tam giác, ô danh nghĩa 5 đơn vị |
| Khoảng hở dựng bề mặt | Đứng tối thiểu 1,5 đơn vị, dự phòng ngang 1,6 |
| Độ dài chặng trên bề mặt bằng Funnel | 142,418721777849 đơn vị mô phỏng |
| Độ dài MMP tham chiếu | 142,418721777849 đơn vị mô phỏng |
| Sai lệch bám tuyến lớn nhất trong lượt đã lưu | Khoảng 0,001819 đơn vị mô phỏng |
| Cao độ chặng bám bề mặt trong lượt đã lưu | Khoảng 7,68–16,57 đơn vị mô phỏng |

Đối chiếu MMP dùng cùng lưới và cùng hai đầu mút của chặng trên bề mặt.
Hai đường đều được kiểm tra thuộc bề mặt. Đây là kiểm chứng số cho ca đã lưu.
Các đoạn tiếp cận bề mặt và hạ tại điểm giao được kiểm tra riêng bằng telemetry.

- [Kết quả đối chiếu MMP](generated/funnel_surface_reference/comparison.md)
- [Số liệu kiểm tra bám bề mặt](generated/funnel_physics/surface_delivery/surface_validation.json)
- [Biểu đồ cao độ](generated/funnel_physics/surface_delivery/surface_altitude_profile.png)
- [Ảnh gần điểm giao](generated/funnel_physics/surface_delivery/city_destination.png)

## Môi trường

- Ubuntu 24.04, hoặc Ubuntu 24.04 trên WSL2 với WSLg để mở giao diện.
- Gazebo Harmonic / Gazebo Sim 8 và Python bindings của hệ thống.
- Python 3.12. Các phiên bản thư viện đã dùng nằm trong `requirements-demo.txt`.

Quy ước hai terminal trong hướng dẫn này:

- **Ubuntu 1** mở Gazebo. Dùng `Ctrl+C` để kết thúc phiên.
- **Ubuntu 2** cài thư viện, lập tuyến, kiểm tra và xuất kết quả.

Mỗi terminal cần ở thư mục gốc của repository. Ví dụ trên máy đang phát triển:

```bash
cd /mnt/c/DroneDemo/drone_gazebo_demo
```

Nếu clone sang vị trí khác, dùng đường dẫn thư mục clone tương ứng.

## Cài đặt một lần

Trong **Ubuntu 2**, tại thư mục gốc repository:

```bash
bash scripts/install_ubuntu.sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
```

Script cài Gazebo cần `sudo` và kết nối mạng. Script này dành cho Ubuntu 24.04.
Các lệnh dưới đây gọi trực tiếp Python trong môi trường ảo, nên có thể dùng
ngay từ terminal mới.

Để chạy phép đối chiếu MMP, cài thêm bộ giải tham chiếu trong **Ubuntu 2**:

```bash
.venv/bin/python -m pip install --no-deps \
  --target generated/funnel_surface_reference/runtime \
  -r requirements-reference.txt
```

Plugin điều khiển trong Gazebo dùng Python hệ thống và các gói `gz` được cài
bằng apt. `scripts/gazebo_system_python.sh` thiết lập môi trường cho tiến trình đó.

## Chạy mô phỏng hiện tại

Đóng phiên Gazebo cũ. Trong **Ubuntu 1**:

```bash
bash scripts/run_funnel_physics.sh surface_delivery
```

Drone bắt đầu tại START đã lưu, tiếp cận bề mặt dẫn đường, lên xuống theo
tuyến Funnel màu cam, rồi hạ thẳng đứng và giữ vị trí trên bục giao màu xanh.
Lượt hiện tại kéo dài khoảng 2 phút 38 giây mô phỏng. Dấu hồng phía trên
drone giúp quan sát khi nhìn toàn thành phố.

Muốn hiện thêm bề mặt dẫn đường trong suốt, chạy trong **Ubuntu 1**:

```bash
bash scripts/run_funnel_physics.sh surface_delivery --show-surface
```

### Hai lệnh chạy riêng cho CPU và GPU

Trong **Ubuntu 1**, chọn một lệnh sau, mỗi lần mở một phiên Gazebo.

GPU qua D3D12 trên WSLg, theo cấu hình đã chạy mượt trên máy phát triển:

```bash
bash scripts/run_surface_gpu.sh
```

CPU qua Mesa llvmpipe, dùng khi cần chạy bằng phần mềm:

```bash
bash scripts/run_surface_cpu.sh
```

Cả hai mặc định chạy `surface_delivery`. Có thể thêm `--show-surface` vào
cuối lệnh. Script GPU xóa thiết lập ép render CPU được kế thừa từ terminal,
còn script CPU đặt rõ `LIBGL_ALWAYS_SOFTWARE=1` và `GALLIUM_DRIVER=llvmpipe`.
Chế độ GPU yêu cầu WSLg và driver hỗ trợ D3D12 trên máy chạy.

Lệnh gốc `run_funnel_physics.sh` dùng driver mặc định của hệ thống. Tùy chọn
`--software` của lệnh gốc bật render CPU. Hai script mới chọn rõ backend đồ
họa cho cùng pipeline lập tuyến và mô phỏng vật lý.

Nhóm sử dụng hai script trong `scripts/` để quản lý cấu hình render. Ca mô
phỏng được chọn bằng biến môi trường. Ví dụ trong **Ubuntu 1**:

```bash
FUNNEL_DEMO_CASE=original bash scripts/run_surface_cpu.sh
```

Repository giữ một bộ dữ liệu đã lập tuyến để chạy ca hiện tại ngay sau cài
đặt. Script luôn tạo lại SDF và đường dẫn tài nguyên theo vị trí clone.
Các tệp SDF chạy thử, log và cache tính toán lớn được tạo cục bộ.

## Kiểm tra sau lượt chạy

Đóng Gazebo, rồi trong **Ubuntu 2**:

```bash
.venv/bin/python tools/analyze_surface_delivery.py
.venv/bin/python tools/compare_surface_geodesic.py
```

Kết quả mong đợi lần lượt là `checks_passed: true` và
`MATCHES_EXACT_REFERENCE`. Dữ liệu lưu tại:

```text
generated/funnel_physics/surface_delivery/surface_validation.json
generated/funnel_physics/surface_delivery/surface_altitude_profile.png
generated/funnel_surface_reference/comparison.json
generated/funnel_surface_reference/comparison.md
```

Trong **Ubuntu 2**, có thể kiểm tra bộ bốn ca phẳng đã lưu:

```bash
.venv/bin/python tools/verify_project_results.py
```

## Lập lại tuyến khi thay đổi bản đồ hoặc thuật toán

Trong **Ubuntu 2**, khi Gazebo đã đóng:

```bash
.venv/bin/python tools/plan_surface_delivery.py --cell 5
.venv/bin/python tools/compare_surface_geodesic.py
```

Sau đó chạy lại mô phỏng trong **Ubuntu 1** và xuất telemetry mới. Bộ lập
tuyến lưu checkpoint cho các nguồn Funnel. Thời gian tính phụ thuộc kích
thước lưới và số nguồn phụ.

Kế hoạch lưu SHA256 của đầu vào và mã liên quan. Nếu sửa một tệp đầu vào,
cần lập lại kế hoạch tương ứng. Khi thay đổi cả pipeline miền phẳng, xem
[hướng dẫn chi tiết](RUNBOOK_CURRENT.md) và các công cụ trong `tools/`.

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
| --- | --- |
| `src/funnel_tree.py` | Lan truyền Funnel, cắt tỉa và tái dựng đường |
| `src/mesh.py` | Lưới tam giác và quan hệ kề |
| `src/trajectory.py` | Tham số hóa thời gian và luật phản hồi |
| `src/funnel_drone_system.py` | Plugin bám tuyến trong Gazebo |
| `tools/plan_surface_delivery.py` | Dựng bề mặt 3D và tính tuyến Funnel |
| `tools/prepare_funnel_physics.py` | Tạo world, route, bục giao và cấu hình giao diện |
| `tools/prepare_city_visual.py` | Phân màu hình học thành phố |
| `tools/compare_surface_geodesic.py` | Đối chiếu với MMP qua pygeodesic |
| `tools/analyze_surface_delivery.py` | Kiểm tra telemetry trên lưới 3D |
| `scripts/` | Cài đặt và mở mô phỏng |
| `assets/city.glb` | Mô hình thành phố kèm nguồn và giấy phép |
| `data/input`, `data/expected` | Năm mesh mẫu và dữ liệu đối chiếu |
| `generated/` | Bộ dữ liệu đã kiểm tra và các kết quả sinh ra |

`RUNBOOK_CURRENT.md` là hướng dẫn vận hành chi tiết. Nhóm lưu quy trình khảo
sát mặt cắt, dựng miền dẫn đường phẳng và thử nghiệm đô thị V3 trong các
README dạng `.txt` để đối chiếu giữa các giai đoạn.

## Phạm vi kết quả

- Mô hình bay hiện là một khối điểm 1 kg điều khiển bằng lực, bù trọng lực,
  feedforward và PD. Rotor là hình minh họa. Điều khiển tư thế, autopilot,
  phần cứng thực và nhiều UAV còn là phần phát triển tiếp theo.
- Lưới bay là bề mặt an toàn dựng phía trên thành phố. Tối ưu được xét trên
  bề mặt đó. Các ô lấy chiều cao lớn nhất và tạo dốc nên khoảng hở có thể
  lớn hơn giá trị tối thiểu.
- Bản đồ được chuẩn hóa về đơn vị mô phỏng. Các kích thước chưa được đối
  chiếu với đo đạc địa lý thực tế. Màu công trình được phân theo hình học.
- Bản cài đặt Funnel còn thực nghiệm. Phần tái dựng trải phẳng dải mặt đã
  chọn. Đối chiếu thành công cho ca hiện tại chưa chứng minh bản cài đặt
  đúng trên mọi lưới.

## Tài liệu tham khảo

Thuật toán dựa trên bài báo của Phan Thanh An, Tran Van Hoai và Vuong Ba Thinh,
*The funnel tree algorithm for finding shortest paths on polyhedral surfaces*,
DOI [10.1080/02331934.2023.2241496](https://doi.org/10.1080/02331934.2023.2241496).
Bộ giải MMP độc lập dùng [pygeodesic](https://github.com/mhogg/pygeodesic).

Mô hình thành phố của **Saigon 3D City**, giấy phép **CC BY 4.0**. Nguồn asset,
các biến đổi và thông tin thuật toán nằm trong [ATTRIBUTION.md](ATTRIBUTION.md).

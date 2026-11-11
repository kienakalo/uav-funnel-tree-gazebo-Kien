# Hướng dẫn hiện tại: demo một UAV bám tuyến Funnel trong Gazebo

Hai lệnh chọn phần đồ họa cho ca hiện tại, chạy trong **Ubuntu 1** sau khi
đóng phiên Gazebo cũ:

```bash
cd /mnt/c/DroneDemo/drone_gazebo_demo
bash scripts/run_surface_gpu.sh
```

Hoặc render bằng CPU:

```bash
bash scripts/run_surface_cpu.sh
```

GPU dùng `GALLIUM_DRIVER=d3d12` trên WSLg. CPU dùng `llvmpipe` và ép software
rendering. Cả hai có thể thêm `--show-surface`. Các lệnh kiểm tra số liệu
trong Ubuntu 2 dùng chung cho hai chế độ.

Nhóm sử dụng Ubuntu 24.04/WSL và Gazebo Harmonic cho các thử nghiệm. Các công
cụ phân tích gọi trực tiếp `.venv/bin/python`; plugin Gazebo sử dụng Python
hệ thống thông qua script thiết lập môi trường riêng.

- **Ubuntu 1:** terminal mở Gazebo. Nhấn `Ctrl+C` ở đây để kết thúc phiên mô phỏng.
- **Ubuntu 2:** terminal chạy kiểm tra và xuất kết quả.
- Ở mỗi terminal, trước tiên chạy `cd /mnt/c/DroneDemo/drone_gazebo_demo`.
- Khi kiểm tra hoặc tổng hợp kết quả cuối cùng, hãy đóng Gazebo để CSV không tiếp tục thay đổi.

## 1. Xem và kiểm tra bộ kết quả đã có

**Ubuntu 1:** giữ Gazebo đóng.

**Ubuntu 2:**

```bash
cd /mnt/c/DroneDemo/drone_gazebo_demo
.venv/bin/python tools/verify_project_results.py
```

Kết quả mong đợi: `Project results: READY`. Đây là kiểm tra nhất quán file và SHA256, không chạy lại mô phỏng.

Save at: C:\DroneDemo\drone_gazebo_demo\generated\final_check\FINAL_RESULTS.md

Save at: C:\DroneDemo\drone_gazebo_demo\generated\final_check\result_manifest.json

## 2. Trình diễn lại một ca trong Gazebo

**Ubuntu 1:** đóng phiên Gazebo cũ, rồi chạy một lệnh dưới đây, mỗi lần một ca:

```bash
bash scripts/run_funnel_physics.sh original
```

Hoặc chọn `cross_city`, `narrow_corridor`, `short_open` thay cho `original`.

| Ca | Giới hạn tốc độ mô phỏng | Thời gian hoàn tất xấp xỉ |
|---|---:|---:|
| original | 5 | 104 giây mô phỏng |
| cross_city | 5 | 80 giây mô phỏng |
| narrow_corridor | 2 | 16 giây mô phỏng |
| short_open | 2 | 24 giây mô phỏng |

Chương trình tự dùng Python hệ thống cho plugin Gazebo, chờ bộ điều khiển nạp xong mới cho mô phỏng chạy. Hai ca ngắn chờ 8 giây và có camera gần hơn. Dấu hồng nằm phía trên drone để dễ quan sát.

Chờ `Route complete; holding final position.`, rồi nhấn `Ctrl+C` ở Ubuntu 1.

Nếu gặp lỗi render, thêm `--software` vào cuối lệnh. Cách này có thể chậm hơn.

### Thử va chạm khi bay thấp

Trong **Ubuntu 1**, đóng phiên Gazebo cũ rồi chạy:

```bash
bash scripts/run_funnel_physics.sh low_collision
```

Camera đặt gần điểm dự kiến va chạm. Drone đợi 5 giây mô phỏng rồi tiếp cận
tường ở cao độ Z = 3,6 đơn vị Gazebo. Đường màu cam là tuyến thử cố ý cắt
qua vật cản. Bộ điều khiển tiếp tục kéo drone về đích, nên drone có thể
dừng hoặc trượt theo mặt va chạm. `Route complete` báo hết lịch di chuyển
của tuyến tham chiếu. Dùng CSV để xem vị trí drone thực sự đạt được.

Trong **Ubuntu 2**, khi Gazebo vẫn mở, đọc một bản tin cảm biến tiếp xúc:

```bash
gz topic -e -n 1 -t /world/funnel_physics_low_collision/model/drone/link/body/sensor/drone_contact/contact
```

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_physics\low_collision\physics_telemetry.csv

### Hạ độ cao tại điểm giao hàng

Trong **Ubuntu 1**, đóng phiên Gazebo cũ rồi chạy:

```bash
bash scripts/run_funnel_physics.sh delivery
```

Drone giữ nguyên START của ca giao hàng trước và đi theo tuyến Funnel màu cam
đến điểm giao xa nhất trong các đỉnh lưới đáp ứng điều kiện đặt bục trên nền
đường, có mặt tiền gần đó và có khoảng hạ trống. Khoảng cách thẳng từ START
đến GOAL khoảng 137,4 đơn vị, tuyến bay ngang khoảng 188,8 đơn vị mô phỏng.
Drone dừng trên
điểm giao rồi hạ thẳng đứng theo vạch xanh lam từ Z ≈ 7,21 xuống Z ≈ 3,99,
cách mặt bục xanh lá 1 đơn vị mô phỏng. Bục nằm trên mặt nền tại Z ≈ 2,89.
Trước khi mở Gazebo, chương trình kiểm tra mặt nền dưới bục và khoảng trống
trong cột hạ. Camera bao quát tuyến từ START đến GOAL.

Nếu sửa lưới hoặc mã Funnel, tạo lại kế hoạch trong **Ubuntu 2**, khi Gazebo
đã đóng:

```bash
.venv/bin/python tools/plan_funnel_delivery.py
```

Kế hoạch ghép các đoạn Funnel trong cache với một lượt lan truyền từ GOAL
mới, rồi kiểm tra toàn tuyến trên lưới. Điểm giao được xếp theo khoảng cách
thẳng từ START giữa các đỉnh lưới đủ điều kiện. Mã lựa chọn dùng lớp nền
đường và các ngưỡng cao độ dành cho asset hiện tại.

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_physics\delivery\horizontal_plan.json

CSV của ca này có `phase=descending` trong đoạn hạ. Ca `delivery` là
minh họa tiếp cận điểm giao riêng, ngoài bộ bốn ca bám tuyến ở mục 3.

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_physics\delivery\physics_telemetry.csv

### Bay bám bề mặt đa diện 3D

Trong **Ubuntu 1**, đóng phiên Gazebo cũ rồi chạy:

```bash
bash scripts/run_funnel_physics.sh surface_delivery
```

Ca này giữ START và vị trí bục giao của ca `delivery`. Drone tiếp cận bề mặt
dẫn đường rồi bám tuyến Funnel 3D màu cam, lên xuống theo các mặt tam giác.
Cuối chặng, drone hạ theo vạch xanh lam sáng để giữ vị trí trên bục. Thành
phố được phân màu theo cao độ và hướng mặt để dễ quan sát. Đây là màu minh
họa theo hình học. Có thể bật bề mặt dẫn đường trong **Ubuntu 1** bằng lệnh:

```bash
bash scripts/run_funnel_physics.sh surface_delivery --show-surface
```

Bề mặt là một bao địa hình và mái nhà có khoảng cách đứng tối thiểu 1,5 đơn
vị mô phỏng, với dự phòng ngang 1,6 cho thân và cánh. Các ô có kích thước
danh nghĩa 5 đơn vị, dùng chiều cao lớn nhất của toàn bộ hình học thành phố
trong ô đã mở rộng. Các đoạn dốc nối cao độ bằng cách nâng các đỉnh lân cận.
Khoảng hở thực tế có thể lớn hơn 1,5 ở vùng chuyển tiếp và ô thô. Thuật toán
Funnel chạy trực tiếp trên lưới 3D này và kiểm tra toàn bộ các đoạn tái dựng
nằm trên bề mặt. Đây là tuyến ứng viên của bản cài đặt thực nghiệm.

Trong **Ubuntu 2**, sau khi đóng Gazebo, kiểm tra telemetry:

```bash
.venv/bin/python tools/analyze_surface_delivery.py
```

Kết quả mong đợi là `checks_passed: true`. Phép kiểm tra so vị trí đo với cao
độ của tam giác chứa hình chiếu XY và kiểm tra khoảng hở bên dưới thân drone
tại các mẫu CSV. Nó tách đoạn tiếp cận và đoạn hạ giao hàng khỏi chặng bám
bề mặt.

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_physics\surface_delivery\surface_validation.json

Nếu thay đổi thành phố hoặc tham số bề mặt, dựng lại trong **Ubuntu 2**:

```bash
.venv/bin/python tools/plan_surface_delivery.py
```

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_physics\surface_delivery\surface_report.json

Trong **Ubuntu 2**, đối chiếu độ dài chặng trên bề mặt với bộ giải trắc địa
MMP độc lập:

```bash
.venv/bin/python tools/compare_surface_geodesic.py
```

Bộ giải `pygeodesic` phiên bản 0.1.11 đã được cài riêng tại
`generated/funnel_surface_reference/runtime`. Kết quả của lưới 858 đỉnh,
1.600 mặt hiện tại là `MATCHES_EXACT_REFERENCE`. Funnel và tham chiếu cùng
có độ dài 142,418721777849 đơn vị mô phỏng. Phép so sánh dùng đúng cùng lưới
và hai đỉnh đầu-cuối của chặng bám bề mặt. Các đoạn tiếp cận bề mặt và hạ
giao hàng được kiểm tra riêng trong mô phỏng.

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_surface_reference\comparison.json

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_surface_reference\comparison.md

## 3. Xuất kết quả sau lượt chạy mới

**Ubuntu 1:** giữ Gazebo đóng.

**Ubuntu 2:** ví dụ cho `cross_city`:

```bash
.venv/bin/python tools/export_funnel_physics_results.py --case cross_city
```

Thay tên ca bằng `original`, `short_open` hoặc `narrow_corridor` khi cần.

Kết quả mong đợi: `checks_passed: true`, `last_phase: complete`, `obstacle_intersecting_sample_segments: []`.

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_physics\cross_city\

Ca `original` dùng trực tiếp thư mục `generated/funnel_physics`; ba ca khác có thư mục con riêng. Mỗi ca có CSV, JSON, hai hình và file tóm tắt.

Sau khi chạy thêm một ca, cần cập nhật lại bảng tổng hợp và kiểm tra cuối vì CSV/metadata đã thay đổi:

```bash
.venv/bin/python tools/summarize_funnel_experiments.py
.venv/bin/python tools/verify_project_results.py
```

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_comparison\

## 4. Chạy lại kiểm tra tìm đường và tham chiếu độc lập

**Ubuntu 1:** giữ Gazebo đóng.

**Ubuntu 2:**

```bash
.venv/bin/python tools/run_funnel_benchmark.py
.venv/bin/python tools/compare_funnel_reference.py
```

Kết quả mong đợi lần lượt: `Complete: True; all cases passed: True` và `All cases match reference: True`.

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_benchmark\

Save at: C:\DroneDemo\drone_gazebo_demo\generated\funnel_reference\

Benchmark có cache. Thời gian của các ca dùng chung cache không phải phép đo hiệu năng độc lập. Nếu đầu vào hoặc mã lập kế hoạch thay đổi, cần chạy lại benchmark, tham chiếu và các lượt mô phỏng liên quan trước khi kết luận cho phiên bản mới.

## Phạm vi của bản demo

Miền bay nằm ngang ở Y = 2 trong hệ tọa độ mô hình gốc. Các tuyến được đổi trục và tỉ lệ nhất quán sang Gazebo. Thuật toán Funnel là bản thực nghiệm; đồ thị nhìn thấy là phép đối chiếu độc lập cho miền phẳng. Mô hình bay dùng khối điểm 1 kg có bù trọng lực và điều khiển lực feedforward + PD; chưa có mô phỏng rotor/autopilot.

Không dùng các kết quả này để khẳng định tối ưu trên mọi mesh, tránh va chạm liên tục theo thời gian hoặc độ chính xác ngoài thực địa.

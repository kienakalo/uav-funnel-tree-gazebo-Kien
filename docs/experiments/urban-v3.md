# Thử nghiệm đô thị V3 trên miền bay phẳng

Tài liệu lịch sử của giai đoạn khảo sát; hướng dẫn hiện tại nằm ở
[README chính](../../README.md) và [runbook](../../RUNBOOK_CURRENT.md).

## Quy trình chạy thử nghiệm

1. `Ctrl+C` ở terminal đang chạy Gazebo, chờ Gazebo đóng.
2. Kiểm tra môi trường Ubuntu 24.04 và các phụ thuộc theo `README.md`.
3. Trong Ubuntu 1:

   ```bash
   cd /mnt/c/DroneDemo/drone_gazebo_demo
   bash scripts/run_urban.sh
   ```

4. Xem tuyến CAM đi vòng; đoạn ĐỎ là đường thẳng bị chặn trong mô hình vùng
   cản. Drone giữ cao độ 9 thay vì 28,54, chạy một chặng có 6 waypoint.
   Nhóm tái sử dụng bộ điều khiển V2; thông báo chạy mang tiền tố `[Drone V2]`.
   Dòng `[Urban V3]` xác nhận tuyến mới đã được tạo.
5. Chờ khoảng một phút MÔ PHỎNG hoặc lâu hơn theo hiệu năng máy, tới dòng:
   `[Drone V2] Route complete; holding final position.`
6. Trong Ubuntu 2:

   ```bash
   cd /mnt/c/DroneDemo/drone_gazebo_demo
   .venv/bin/python tools/analyze_telemetry.py
   .venv/bin/python tools/check_urban_flight.py
   ```

   Hai công cụ đánh giá sai lệch bám tuyến và vùng cản từ dữ liệu đo.

Script tự lưu bản sao CSV cũ thành
`generated/physics_telemetry_before_urban_<thời gian>.csv` trước khi bắt đầu mô
phỏng mới. Không mở hai Gazebo cùng lúc.

- Nếu lỗi render: `bash scripts/run_urban.sh --software`
- Muốn quay về bản cao độ cũ: đóng phiên hiện tại, chạy
  `bash scripts/run.sh physics`.
- Hồi quy thuật toán trong Ubuntu 2: `.venv/bin/python check.py`.

## Phương pháp

- Giữ bản đồ chuẩn hóa đã có (không phải tọa độ đo đạc theo mét).
- Mỗi tam giác công trình có độ cao >= 9-3,5 tạo một hộp chiếu XY và mở rộng
  3,5 theo hai trục. Đây là các cột cản bảo thủ, có thể chặn cả vùng thực tế
  trống.
- Raster hóa toàn ô có giao với hộp mở rộng, chọn các ô trống nối nhau.
- A* chọn hành lang trên grid 1 đơn vị; triangulate hành lang thành 170 mặt.
- Funnel Tree thử nghiệm tính đường trong hành lang, có xử lý cusp tại đỉnh
  biên phản xạ, ghi nhận đích trước cập nhật tại chỗ và kiểm tra truy hồi.
- Gộp các điểm thẳng hàng; giữ 6 waypoint, chiều dài khoảng 78,835 so với
  đường thẳng 53,767. Không khẳng định tối ưu toàn cục trên thành phố.
- Kiểm tra liên tục đoạn thẳng với các hộp mở rộng và đoạn nằm trên mesh hành
  lang trước khi xuất world. Nếu không tìm được tuyến qua kiểm tra, báo lỗi.
- Dùng nguyên bộ điều khiển V2 để giảm tốc và dừng ở góc, không nội suy bo góc
  ra ngoài hành lang. Tốc độ tham chiếu tối đa 3 đơn vị/giây.

## Khoảng cách và phạm vi kiểm chứng

Các tam giác bị bỏ qua thấp hơn tuyến ít nhất 3,5 theo Z; các tam giác còn lại
được tránh bằng hình chiếu hộp mở rộng 3,5 theo XY. Với mô hình bất động và
đường danh định đúng cao độ, đây là cận bảo thủ theo dữ liệu mesh; chưa phải
chứng nhận an toàn ngoài thực địa. Drone minh họa có bán kính bao hình xấp xỉ
2,72; khoảng đệm còn lại dành cho sai lệch bám đường trong mô phỏng.

`check_urban_flight` dùng các đoạn nối mẫu vị trí trong CSV 10 Hz để kiểm tra
lại vùng cản. Nó không đọc contact sensor Gazebo và không chứng minh mọi điểm
của chuyển động thật giữa hai mẫu đều không va chạm. Không có vật cản động.

## Đã kiểm tra

- Bộ mesh cũ, star nguồn 1, mặt phẳng mọi cặp đỉnh và các nhánh quy tắc clip.
- Mặt mở hình L có đường ngắn nhất phải đi qua góc lõm, so với đáp án giải tích.
- Tuyến đô thị nằm trên hành lang; đường trực tiếp bị cản; các đoạn kế hoạch
  không cắt hộp công trình đã mở rộng.
- Tích phân số khối điểm với bộ điều khiển V2; xem
  `offline_urban_validation.json`.
- Kiểm tra tạo world và cú pháp Python/shell.

Kết quả tích phân ngoại tuyến được lưu trong `offline_urban_validation.json`.
Các chỉ số của từng lượt Gazebo được tính từ telemetry của lượt đó.

## Khác biệt với mục tiêu nghiên cứu cuối

Chưa áp dụng Funnel Tree lên toàn bộ vỏ công trình 301.490 tam giác; bản đồ
được dùng làm vật cản để tạo bề mặt dẫn đường tại cao độ cố định. A* chọn hành
lang nên kết quả chỉ xét trong hành lang đó, có thể dài hơn một tuyến ở hành
lang khác. Chưa có rotor/autopilot, nhiều UAV hoặc vật cản động.

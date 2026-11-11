SỬA THỐNG KÊ ĐỘ CAO - KHÔNG CẦN CÀI THÊM

Giải nén nội dung vào C:\DroneDemo\drone_gazebo_demo.
File mới ở tools/inspect_flight_levels_fixed.py, không ghi đè script cũ.

Ở Ubuntu 2, giữ môi trường (.venv), chạy:
cd /mnt/c/DroneDemo/drone_gazebo_demo
python tools/inspect_flight_levels_fixed.py

Mặc định tìm data/input/city.glb trước, rồi assets/city.glb.
Nếu muốn chỉ định rõ:
python tools/inspect_flight_levels_fixed.py --city data/input/city.glb

Kết quả mới:
generated/flight_level_candidates_fixed.csv
generated/city_object_height_bounds_fixed.csv
generated/flight_levels_fixed_metadata.json
Các kết quả cũ giữ nguyên để đối chiếu. Gửi bảng log mới để tiếp tục chọn mặt cắt.

LỖI CŨ
Đoạn thống kê mức bay lọc bằng mesh.bounds ở local coordinates trước khi áp dụng
scene transform. Vì vậy đã loại nhầm phần lớn objects. Script mới áp dụng đầy đủ
transform của scene graph rồi mới lấy bounds và kiểm tra tam giác trên cùng hệ.
Bounds giao mức cao chỉ là bước lọc thô; một Object chứa nhiều mảnh rời có thể có
bounds bao quanh mức đó mà không có tam giác thực sự giao mặt phẳng.

ĐƠN VỊ VÀ GIỚI HẠN
Y trong kết quả là độ cao trong scene GLB gốc, chưa xác nhận theo mét.
Demo Gazebo cũ đổi sang Z-up, dịch gốc và scale riêng. Không lấy số Y=2 gán trực
tiếp thành Z=2 trong Gazebo; cần phép biến đổi nhất quán.
Object là nhóm hình học, không đồng nghĩa một tòa nhà. Số tam giác giao mặt phẳng
không đo diện tích bị cản, liên thông vùng trống hoặc khoảng cách thân UAV.
Giao tuyến vỏ công trình có thể không kín do asset; chưa phải footprint đã sửa topology.

Script dùng NumPy để đọc các primitive GLB2 không nén của asset hiện tại.
Không đổi tỉ lệ, không weld/làm sạch lưới, không cài đặt thêm và không chạy Gazebo.
Đã kiểm tra kết quả so với phép tính độc lập qua bộ nạp bản đồ của demo.
reference_fixed.json chứa số tham chiếu từ city.glb đã gửi, không phải số đo bay.

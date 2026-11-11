TRÍCH MẶT CẮT THÀNH PHỐ TẠI Y = 2,0

Giải nén vào C:\DroneDemo\drone_gazebo_demo.
Ở Ubuntu 2, giữ môi trường (.venv), chạy:
cd /mnt/c/DroneDemo/drone_gazebo_demo
python tools/build_flight_slice.py --height 2

Script tìm data/input/city.glb trước, rồi assets/city.glb.
Để chỉ định rõ file:
python tools/build_flight_slice.py --height 2 --city data/input/city.glb

Kết quả mới trong generated:
- flight_slice_y2p00.png: mặt cắt nhìn theo mặt phẳng X/Z.
- flight_slice_y2p00.json: các đỉnh, cạnh và component để xử lý tiếp.
- flight_slice_y2p00_report.json: thống kê và hệ tọa độ.

Mở kết quả bằng:
explorer.exe "$(wslpath -w generated)"

Đã tính trên city.glb gốc: 44 object, 3.584 tam giác crossing, 3.579 đoạn thô,
3.571 cạnh không trùng, 120 component, 76 component dạng chu trình bậc 2 và
44 component hở hoặc có nhánh. Kết quả tham chiếu có sẵn trong reference/.
Script được thử với tam giác cắt biết trước, tiếp xúc tại đỉnh và các đồ thị
đường bao kín/hở đơn giản, đồng thời chạy trên toàn bộ asset đã gửi.

MÀU SẮC
Xanh: component có tất cả đỉnh bậc 2, ứng viên đường bao kín.
Cam: component hở hoặc có nhánh, cần kiểm tra trước khi tạo polygon.
Xám nhạt: hình chiếu lấy mẫu của thành phố để định hướng, không phải vùng bay.

GIỚI HẠN
- Y-up và đơn vị scene GLB gốc; không đổi trục hoặc scale Gazebo, chưa xác nhận mét.
- Điểm đầu/cuối được gộp bằng lượng tử hóa 1e-5 đơn vị; số component có thể phụ
  thuộc ngưỡng. Đây không phải sửa topology chính xác theo mọi khoảng cách.
- Chu trình bậc 2 chưa đảm bảo polygon đơn, không tự cắt, không lồng nhau hoặc
  đúng là đường bao ngoài công trình. Chưa tự phân loại lỗ bên trong polygon.
- Nếu có tam giác đồng phẳng với mặt cắt, các cạnh được xuất và đánh dấu trong
  thống kê; chưa khử cạnh trong để dựng biên của toàn mảng đồng phẳng.
- Component hở/có nhánh không bị xóa hoặc tự nối giả định thành vòng kín.
- Chưa tạo miền bay, nới vật cản theo kích thước drone hoặc tam giác hóa.
- Không thay route/world Gazebo cũ và không sửa file bản đồ gốc.

Phụ thuộc: NumPy và Matplotlib trong môi trường phân tích đang dùng.
Nếu thiếu Matplotlib, dùng python -m pip install matplotlib trong (.venv).

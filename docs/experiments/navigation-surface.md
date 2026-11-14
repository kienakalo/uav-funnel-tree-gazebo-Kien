# Dựng miền dẫn đường phẳng và tam giác hóa

Tài liệu lịch sử của giai đoạn khảo sát; hướng dẫn hiện tại nằm ở
[README chính](../../README.md) và [runbook](../../RUNBOOK_CURRENT.md).

Nhóm xây dựng miền dẫn đường phẳng từ các vùng trống của mặt cắt thành phố.
Quy trình thực hiện trong Ubuntu 2:

```bash
cd /mnt/c/DroneDemo/drone_gazebo_demo
.venv/bin/python tools/build_navigation_surface.py --height 2
```

Công cụ xử lý ngoại tuyến, sử dụng NumPy và Matplotlib của môi trường phân
tích. File `city.glb` được đọc tại `data/source/city.glb`. Có thể
chỉ định rõ:

```bash
.venv/bin/python tools/build_navigation_surface.py --height 2 --city data/source/city.glb
```

## Kết quả

- `generated/navigation_y2p00.png`: vùng cản và lưới nhìn từ trên xuống.
- `generated/navigation_y2p00.geom`: thành phần miền bay lớn nhất, tọa độ Y-up.
- `generated/navigation_y2p00_report.json`: tham số, số liệu và kết quả kiểm tra.
- `generated/navigation_y2p00_grid.npz`: grid và nhãn liên thông để chọn điểm sau.

Mở thư mục kết quả:

```bash
explorer.exe "$(wslpath -w generated)"
```

Kết quả khảo sát trên mô hình thành phố:

- 4 thành phần miền trống; chọn thành phần lớn nhất gồm 7.678 ô.
- 8.236 đỉnh, 15.356 tam giác, 23.597 cạnh; 1.126 cạnh biên.
- Không cạnh phi đa tạp, không đỉnh biên có bậc sai, không quạt mặt rời tại
  đỉnh, không tam giác suy biến. Các ô giữ lại không giao hộp vật cản đã mở
  rộng.
- Diện tích thành phần được chọn: 1.919,5 đơn vị mô hình bình phương.

## Ý nghĩa màu

- **Cam:** hình chiếu công trình được mở rộng, mô hình hóa thành cột cản.
- **Xanh lá có lưới:** thành phần miền dẫn đường được xuất ra `.geom`.
- **Xanh nhạt:** các thành phần trống khác, không đưa vào mesh chính.
- **Xám:** vùng loại ở rìa asset hoặc các ô loại để tránh chỉ tiếp xúc tại điểm.

## Vì sao không chỉ giữ 76 vòng kín?

Bản đồ còn 44 component đường cắt hở/có nhánh. Nếu chỉ lấy vòng kín, có thể bỏ
sót vật cản. Bước này dùng cách khác đã ghi rõ trong report: lấy các tam giác
có điểm cao nhất >= Y_bay - khoảng đệm dọc, chiếu hộp bao của chúng xuống X/Z,
nới hộp theo khoảng đệm ngang và coi toàn bộ cột đó là cản. Không tự nối các
đường hở. Các mái cao cũng tạo cột cản, giúp không chọn nhầm nội thất rỗng bên
trong vỏ công trình làm miền bay. Đây là phương pháp bảo thủ, chưa phải tái
dựng footprint hình học chính xác hoặc sửa toàn bộ topology của `city.glb`.

## Tham số mặc định (đơn vị mô hình, chưa phải mét)

Y = 2; khoảng đệm ngang = 1; khoảng đệm dọc = 0,2; cạnh ô = 0,5.

Đây là giả định minh họa cho bước chuẩn bị dữ liệu, chưa xác nhận kích thước
UAV thực. Khoảng đệm dọc là giới hạn nửa chiều cao thiết bị + biên dự phòng
trong hệ Y-up; khoảng đệm ngang phải bao cả thân/cánh theo phương ngang.

Mỗi ô phải không giao cả hộp đã mở rộng mới được giữ. Vì vậy đường chéo của ô
và tam giác đều nằm trong miền trống theo mô hình cột cản. Không kiểm tra riêng
tâm ô rồi bỏ qua phần cạnh. Điểm tiếp xúc chéo giữa hai ô không tạo đường bay;
nếu có cấu hình tiếp xúc chéo, chương trình loại thêm ô và ghi số lượng.

## Phạm vi

- Một mặt phẳng có lỗ/vật cản, là trường hợp 2D của bài toán trên bề mặt.
- Không có đường đi hay kết luận tối ưu ở bước này. Chưa chạy Funnel Tree trên
  toàn bộ 15.356 mặt vì cần kiểm tra hiệu năng và phạm vi hỗ trợ bề mặt có biên.
- Chưa sửa world/route Gazebo. Định dạng `.geom` vẫn dùng (X,Y,Z) với Y là độ
  cao; cần đổi trục và tỉ lệ nhất quán trước khi dùng làm quỹ đạo Gazebo Z-up.
- Vùng cản bao cả không gian dưới mái và có thể chặn cầu/hầm/lối thực tế trống.
  Số liệu này không đại diện diện tích tự do chính xác của đô thị ngoài thực địa.
- Chỉ kiểm tra so với hình học asset đã có, không chứng nhận an toàn cho UAV thật.

## Kiểm tra đã thực hiện

Đã thử raster tại biên ô chính xác, cấu hình hai ô chạm chéo và lưới chữ L;
chạy toàn bộ asset, kiểm tra mọi ô giữ lại với toàn bộ hộp cản; kiểm tra cạnh,
biên và quạt mặt ở từng đỉnh; xem hình xuất ra. File reference có kết quả chạy.

## Bước sau

Chọn một vùng/điểm đầu-đích nhỏ trong miền vừa tạo, kiểm chứng đường đi của
Funnel Tree và so sánh với một phương pháp tham chiếu độc lập trước khi mô
phỏng.

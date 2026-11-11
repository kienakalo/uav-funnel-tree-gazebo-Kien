# Tổng hợp 4 ca mô phỏng bám tuyến Funnel

Kết quả: **4/4 ca đạt**. Mỗi ca đã được kiểm tra lại từ CSV đo trong Gazebo.

| Ca thử | Độ dài (mô hình gốc) | Giới hạn tốc độ | Sai lệch lớn nhất | RMSE khi di chuyển | Sai lệch cuối tới GOAL |
|---|---:|---:|---:|---:|---:|
| Tuyến ban đầu (`original`) | 68.088655 | 5.0 | 0.002005475 | 0.000810660 | 2.047e-07 |
| Vùng thoáng (`short_open`) | 4.146551 | 2.0 | 0.000524785 | 0.000370956 | 1.023e-06 |
| Vòng vật cản trung tâm (`cross_city`) | 51.896852 | 5.0 | 0.002542982 | 0.000872783 | 2.143e-07 |
| Hành lang hẹp (`narrow_corridor`) | 1.840894 | 2.0 | 0.000941926 | 0.000639369 | 2.767e-07 |

Độ dài dùng đơn vị mô hình gốc. Sai lệch dùng đơn vị mô phỏng; tốc độ dùng đơn vị mô phỏng/giây.

| Ca thử | Độ dài mô phỏng | Tốc độ đo lớn nhất | Thời điểm hoàn tất (giây mô phỏng) | Số mẫu | Số đoạn nối mẫu giao cột cản |
|---|---:|---:|---:|---:|---:|
| original | 245.310911 | 4.999903 | 104.202 | 2984 | 0 |
| short_open | 14.939263 | 1.999615 | 23.546 | 839 | 0 |
| cross_city | 186.974819 | 4.999769 | 80.320 | 1875 | 0 |
| narrow_corridor | 6.632401 | 1.999560 | 15.762 | 522 | 0 |

## Nhận xét

- Cả bốn lượt đã tới trạng thái `complete`; sai lệch bám tuyến nhỏ trong mô hình đang dùng.
- Thời điểm hoàn tất lấy từ mẫu CSV đầu tiên có trạng thái `complete`, không cộng thời gian tiếp tục giữ vị trí ở đích.
- RMSE chỉ tính các mẫu có trạng thái `moving`, tránh làm kết quả thấp đi do thời gian chờ hoặc giữ vị trí kéo dài.
- Hai ca dài có giới hạn tốc độ 5; hai ca ngắn có giới hạn 2 và thời gian chờ ban đầu dài hơn. Các số liệu không phải phép so sánh công bằng về hiệu năng thuật toán hoặc chất lượng bộ điều khiển.

## Phạm vi kết luận

- Drone là khối điểm 1 kg có bù trọng lực và điều khiển lực feedforward + PD; chưa có lực đẩy từng rotor, attitude controller hay autopilot.
- Không phát hiện giao với mô hình cột cản đã mở rộng ở các đoạn thẳng nối mẫu đo. Đây không phải chứng minh tránh va chạm liên tục theo thời gian hay bằng cảm biến tiếp xúc.
- Bản đồ được chuẩn hóa tỉ lệ để mô phỏng; không quy đổi các sai lệch trên thành độ chính xác ngoài thực địa.
- Bốn ca đạt là bằng chứng thực nghiệm trong bộ thử này, chưa chứng nhận Funnel Tree đúng/tối ưu trên mọi bản đồ hoặc tuyến ngắn nhất toàn cục.

## Dữ liệu nguồn

Các đường dẫn và SHA256 của route, telemetry và báo cáo kiểm tra được ghi trong `comparison_results.json`.

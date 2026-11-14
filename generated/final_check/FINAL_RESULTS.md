# Kết quả đã kiểm tra của demo một UAV

**Trạng thái bộ file: READY.** Các báo cáo tìm đường, bám tuyến và đối chiếu tham chiếu của 4 ca nhất quán với dữ liệu nguồn hiện có.

Lần kiểm tra này chỉ kiểm tra tính nhất quán file và SHA256; không chạy lại Gazebo hoặc chứng minh hình học.

| Ca thử | Độ dài mô hình gốc | Độ dài tham chiếu | Sai lệch bám tuyến lớn nhất | RMSE khi di chuyển |
|---|---:|---:|---:|---:|
| original | 68.088655 | 68.088655 | 0.002005475 | 0.000810660 |
| short_open | 4.146551 | 4.146551 | 0.000524785 | 0.000370956 |
| cross_city | 51.896852 | 51.896852 | 0.002542982 | 0.000872783 |
| narrow_corridor | 1.840894 | 1.840894 | 0.000941926 | 0.000639369 |

## Kết luận có thể sử dụng

Trên bốn ca thử đã chọn của miền dẫn đường phẳng Y = 2, các tuyến Funnel thực nghiệm nằm trong miền và có độ dài khớp phương pháp tham chiếu độc lập trong dung sai số. Mô hình khối điểm điều khiển bằng lực đã hoàn tất các tuyến với sai lệch bám tuyến nhỏ. Không phát hiện giao với cột cản đã mở rộng ở các đoạn thẳng nối mẫu vị trí đo được.

## Giới hạn cần nêu trong báo cáo

- Bằng chứng áp dụng cho bốn ca trên miền bay hiện tại; không chứng nhận thuật toán đúng/tối ưu trên mọi mesh hoặc bài toán tìm đường 3D.
- Mô hình động lực học là khối điểm 1 kg có bù trọng lực và điều khiển feedforward + PD. Chưa mô phỏng lực đẩy riêng từng rotor, attitude controller hay autopilot.
- Các đoạn nối mẫu CSV không phải chứng minh tránh va chạm liên tục theo thời gian.
- Hai ca dài có giới hạn tốc độ 5, hai ca ngắn có giới hạn 2; không dùng bảng sai lệch để xếp hạng công bằng giữa các ca.
- Đơn vị bản đồ và mô phỏng được chuẩn hóa từ asset, không phải tọa độ địa lý đo đạc.

## File cần dùng khi viết báo cáo

- `generated/funnel_benchmark/benchmark_routes.png`: bốn ca tìm đường.
- `generated/funnel_comparison/comparison_report.md`: bảng kết quả bám tuyến.
- `generated/funnel_comparison/comparison_chart.png`: biểu đồ sai lệch và tốc độ.
- `generated/funnel_reference/reference_comparison.md`: bảng đối chiếu độ dài.
- `generated/funnel_reference/reference_routes.png`: tuyến Funnel và tuyến tham chiếu.
- `generated/final_check/result_manifest.json`: SHA256 và dữ liệu kết luận.

Quy trình chạy lại và quy ước Ubuntu 1/Ubuntu 2 nằm trong `RUNBOOK_CURRENT.md` ở thư mục gốc dự án.

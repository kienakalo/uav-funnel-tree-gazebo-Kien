# Ảnh hưởng của kích thước ô

Giữ nguyên mô hình thành phố, miền ngang, tọa độ START và điểm giao hàng; khoảng hở đứng 1,5, dự phòng ngang 1,6 và hệ số dốc theo trục 0,5.
Cao độ hai đầu chặng geodesic thay đổi theo bề mặt. Vì vậy đây là so sánh các miền tối ưu khác nhau, không phải kiểm tra hội tụ trên một bề mặt cố định.

| Ô | Đỉnh | Tam giác | Funnel | MMP | Tổng hình học nhiệm vụ | Thời gian Funnel (s) | Nguồn | Nút cây mới | Peak RSS tiến trình (MiB) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 2295 | 4400 | 142.418722 | 142.418722 | 148.815255 | 308.964 | 49 | 224682 | 512.7 |
| 7.5 | 1085 | 2040 | 142.065980 | 142.065980 | 150.138147 | 43.500 | 23 | 50004 | 269.0 |
| 15 | 323 | 576 | 140.007515 | 140.007515 | 149.706565 | 0.750 | 4 | 2612 | 262.6 |

Mỗi cấu hình được tính trong một tiến trình riêng, cache mới. Chỉ đo một lượt; thời gian gồm ghi checkpoint, không suy ra mức tăng tốc thống kê.
Peak RSS là high-water mark của cả tiến trình đến sau MMP, không phải bộ nhớ riêng của Funnel.
Thí nghiệm này kiểm tra hình học và MMP, chưa chạy lại mô phỏng bám tuyến cho từng kích thước ô.

Background GUI/render workloads were not controlled; wall times are observational, not an isolated algorithm-only benchmark.

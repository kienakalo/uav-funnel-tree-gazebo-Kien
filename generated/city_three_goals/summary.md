# Ba tuyến trên cùng bề mặt thành phố

Ba truy vấn độc lập, cùng START và cùng SHA256 lưới. Không phải hành trình ghé ba đích.
Đối chiếu MMP chỉ gồm chặng trên bề mặt; mô phỏng gồm tiếp cận và hạ giao hàng.

| Ca | Funnel | MMP | Thời gian kế hoạch bay (s) | Sai số bám lớn nhất | Khoảng hở lấy mẫu nhỏ nhất |
| --- | ---: | ---: | ---: | ---: | ---: |
| g1 | 142.418721778 | 142.418721778 | 100.664 | 0.002363 | 1.099998 |
| g2 | 125.636332762 | 125.636332762 | 99.280 | 0.002451 | 1.099998 |
| g3 | 86.152327598 | 86.152327598 | 94.414 | 0.002243 | 1.100001 |

Thời gian lập tuyến trong JSON là các truy vấn nối tiếp dùng chung cache, bao gồm ghi checkpoint; không dùng để so sánh hiệu năng cold-start.
Mô phỏng khối điểm 1 kg trong Gazebo không giao diện, bước vật lý 0,002 s. Khoảng hở là kiểm tra lấy mẫu, không phải chứng minh va chạm liên tục.
Khớp MMP là kiểm chứng số cho ba ca trên bề mặt an toàn đã dựng, không phải chứng minh đúng tổng quát cho mọi lưới.

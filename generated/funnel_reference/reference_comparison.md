# Đối chiếu tuyến Funnel với phương pháp độc lập

Tham chiếu: đồ thị nhìn thấy giữa các góc biên của miền đa giác, gồm cả các lỗ, và START/GOAL.
Đồ thị tham chiếu không dùng lan truyền Funnel hoặc đường đi theo cạnh lưới. Không nới miền dẫn đường khi tính tuyến tham chiếu.

| Ca thử | Funnel | Tham chiếu | Chênh lệch (%) | Kết quả |
|---|---:|---:|---:|---|
| original | 68.088654835 | 68.088654835 | 0.000000 | MATCHES_REFERENCE |
| short_open | 4.146551445 | 4.146551445 | 0.000000 | MATCHES_REFERENCE |
| cross_city | 51.896851513 | 51.896851513 | -0.000000 | MATCHES_REFERENCE |
| narrow_corridor | 1.840893503 | 1.840893503 | 0.000000 | MATCHES_REFERENCE |

Độ dài dùng đơn vị mô hình gốc.

`MATCHES_REFERENCE`: độ dài trùng trong dung sai số. `LONGER_THAN_REFERENCE`: tuyến Funnel hợp lệ nhưng dài hơn tham chiếu. `INCONSISTENT`: cần điều tra tính hợp lệ hoặc sai lệch số.

Kết quả là đối chiếu số cho bốn ca trên miền bay phẳng đã tạo. Không chứng nhận thuật toán Funnel thực nghiệm đúng trên mọi mesh hoặc bài toán 3D.
Các tuyến Gazebo hiện có không bị thay đổi.

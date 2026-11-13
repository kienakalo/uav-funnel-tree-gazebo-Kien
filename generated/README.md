# Dữ liệu và kết quả thực nghiệm

Các chương trình ghi đầu ra vào thư mục này. `.gitignore` chỉ giữ bộ dữ liệu
và kết quả được chọn để chạy lại demo và đối chiếu; log, cache lan truyền,
thư viện cài cục bộ và các bản chạy trung gian được bỏ qua.

## Demo hiện tại

| Thư mục | Nội dung |
| --- | --- |
| `funnel_physics/surface_delivery/` | Lưới 3D, kế hoạch, tuyến bay, telemetry, kiểm tra bám bề mặt và hình minh họa |
| `funnel_surface_reference/` | Tuyến MMP độc lập và kết quả đối chiếu trên cùng lưới |
| `funnel_preview/` | Hình học thành phố và cấu hình được dùng trong quy trình dựng demo |

Lệnh chạy nằm trong [README chính](../README.md). Thư mục này có cả dữ liệu
đầu vào cho các bước sau; cần kiểm tra phụ thuộc trước khi xóa hoặc đổi tên.

## Thí nghiệm một START đến ba đích

Thí nghiệm một START đến ba đích trên cùng lưới 3D nằm tại
[`city_three_goals/`](city_three_goals/): `cases.json` lưu điểm đầu/đích,
`results.json` và `summary.md` tổng hợp, `routes.png` minh họa ba tuyến.
Mỗi thư mục `g1`, `g2`, `g3` chứa kế hoạch, đối chiếu MMP và kết quả Gazebo
riêng. Cache lan truyền và world dựng lại vẫn được bỏ qua bởi Git.

## Các giai đoạn thực nghiệm trước

- `funnel_benchmark/`: bốn ca kiểm tra hình học trên miền dẫn đường phẳng.
- `funnel_reference/`: đối chiếu tham chiếu cho các ca phẳng.
- `funnel_comparison/`: tổng hợp kết quả bám tuyến của bốn ca.
- Các ca khác trong `funnel_physics/`: thử nghiệm tuyến phẳng, giao hàng và va chạm.
- `final_check/`: bản tổng hợp và dấu vân tay của bộ kết quả phẳng đã lưu.
  Phạm vi của bộ này khác với ca bám bề mặt 3D hiện tại.

Các kết quả cũ được giữ để đối chiếu và phục vụ các phụ thuộc đang có.
Chạy mô phỏng hoặc phân tích lại có thể cập nhật telemetry, hình và JSON;
cần lưu cùng bộ kết quả tương ứng khi tạo một mốc thực nghiệm mới.

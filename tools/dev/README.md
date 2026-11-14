# Công cụ khảo sát và bảo trì

Các script ở đây phục vụ khảo sát hình học thành phố và các bước sửa mã
trong quá trình phát triển. Chúng không nằm trong lệnh chạy demo hiện tại.
Chạy từ thư mục gốc repository vì các đường dẫn dữ liệu được tính từ đó.

- `inspect_*.py`: khảo sát cao độ, liên thông và cấu trúc lưới.
- `extract_city_components*.py`: trích thành phần hình học để khảo sát.
- `fix_funnel_angle_roles.py`: bản vá lịch sử cho vai trò hai góc Funnel;
  mã nguồn hiện tại đã có sửa đổi này.

Một số công cụ khảo sát cũ dùng `trimesh` và đường dẫn
`data/source/city.glb`. Khi sử dụng lại, cần cung cấp mô hình ở đường dẫn đó
hoặc điều chỉnh biến `CITY` theo dữ liệu khảo sát. Không cần chạy các công
cụ này để mở demo bám bề mặt.

`tools/inspect_flight_levels_fixed.py` vẫn ở thư mục cha vì được các bước
dựng bản đồ và phân tích sử dụng như một module.

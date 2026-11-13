# Các giai đoạn thử nghiệm

Thư mục này lưu quy trình khảo sát và các phương án đã thử trong quá trình
phát triển. Hướng dẫn chạy demo bám bề mặt 3D hiện tại nằm trong
[README chính](../../README.md) và [runbook](../../RUNBOOK_CURRENT.md).

| Tài liệu | Nội dung |
| --- | --- |
| [Khảo sát cao độ](README.txt) | Phân tích cao độ mô hình thành phố |
| [Miền dẫn đường](README_NAVIGATION.txt) | Thử nghiệm dựng miền dẫn đường phẳng |
| [Mặt cắt](README_SLICE.txt) | Thử nghiệm mặt cắt mô hình |
| [Đô thị V3](README_URBAN_V3.txt) | Quy trình thử nghiệm đô thị V3 |

Mọi lệnh trong các tài liệu này chạy từ thư mục gốc repository. Một số
bước cần dữ liệu trung gian hoặc thư viện khảo sát ngoài bộ cài demo hiện tại.
Các công cụ khảo sát độc lập đã được chuyển vào `tools/dev/`; module
`tools/inspect_flight_levels_fixed.py` vẫn ở vị trí cũ vì được pipeline sử dụng.

# Kiểm thử hồi quy

Chạy tại thư mục gốc repository trong môi trường Ubuntu đã cài thư viện:

```bash
.venv/bin/python tests/test_funnel_clip.py
.venv/bin/python tests/test_funnel_target_scope.py
.venv/bin/python tests/test_pose_retries.py
```

Các kiểm thử lần lượt kiểm tra thủ tục cắt tỉa, việc giới hạn đỉnh đích và
xử lý lỗi tạm thời khi gọi dịch vụ pose. Kiểm thử pose dùng dịch vụ giả lập,
không cần mở Gazebo.

`tools/test_funnel_initialization.py` là công cụ xuất báo cáo cấu trúc cây
ban đầu từ dữ liệu khảo sát, nên vẫn nằm cùng các công cụ tạo dữ liệu.

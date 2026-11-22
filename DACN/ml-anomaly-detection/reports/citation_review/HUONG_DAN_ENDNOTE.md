# Thư viện nguồn cho EndNote và báo cáo IEEE

Đã tạo 12 bản ghi RIS theo thứ tự xuất hiện của báo cáo tại Google Docs. Tệp RIS lưu thông tin nguồn và liên kết; không nhúng bản PDF có bản quyền.

1. Trong EndNote, mở hoặc tạo thư viện của bạn; nhập tệp tai_lieu_tham_khao_ieee.ris bằng chức năng Import và bộ lọc Reference Manager (RIS)/RefMan RIS.
2. Kiểm tra tác giả, dấu tiếng Việt, DOI, loại tài liệu, article number và trang sau khi nhập. Các nguồn tổ chức được ghi theo corporate author với dấu phẩy cuối. Hai bài ACM dùng article number 15/56; thông tin này còn nằm trong Notes nếu bộ lọc chưa ánh xạ đúng.
3. Chọn output style IEEE. Đối chiếu kết quả với danh_muc_ieee.txt và quy định của trường; số nguồn được quyết định theo lần xuất hiện trong bài, không theo alphabet.
4. Nếu dùng Word có Cite While You Write, chèn lại các trích dẫn từ thư viện rồi cập nhật bibliography; giữ bản Google Docs hiện tại để đối chiếu.

## Giới hạn cần biết

Bản chỉnh trong Google Docs là trích dẫn văn bản tĩnh, có liên kết nguồn và định dạng IEEE. Chưa tạo thư viện .enl hoặc trường trích dẫn sống do EndNote quản lý; chưa chạy kiểm tra nhập trong phần mềm EndNote. Tệp RIS là dữ liệu chuẩn bị để bạn nhập, không chứng minh đã liên kết EndNote với Google Docs. Không tự chuyển đổi tài liệu hoặc thay thế file gốc.

## Nguồn hướng dẫn chính thức

- EndNote Import Filters (có RefMan RIS): https://endnote.com/downloads/filters/
- EndNote Import Options: https://docs.endnote.com/docs/endnote/2025/v1/macos/en/content/08import/import_options.htm
- IEEE Reference Guide: https://ieeeauthorcenter.ieee.org/wp-content/uploads/IEEE-Reference-Guide.pdf
- Link SGU người dùng cung cấp hiện chuyển về trang chủ tạp chí. Quy tắc đã áp dụng theo nội dung người dùng gửi và IEEE Reference Guide.

## Những sửa đổi chính

Thứ tự trích dẫn cũ là 1,2,6,4,12,5,13,14. Bản mới dùng 12 nguồn có trích dẫn thực tế; bỏ DBSCAN, sách Aggarwal và PyOD khỏi danh mục báo cáo này vì không dùng để lập luận hoặc triển khai. Thêm nguồn NIST cho modified Z-score. Bài Ahmad, NAB và bài scikit-learn đã được dẫn trong các đoạn phù hợp. Tất cả số liệu từ bài báo được ghi riêng tại mục 2.4; Chương 4 dùng kết quả tự chạy có lưu CSV/JSON.


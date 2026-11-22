# Trợ lý quản trị viên và thông báo email

Mở ứng dụng bằng `CHAY_UNG_DUNG.bat`, chọn **Giám sát trực tuyến → Giám sát &
Cảnh báo → Trợ lý AI & Email**. Trợ lý đọc các cảnh báo mà bốn thuật toán đã
chấm và lưu, không thay kết quả dự đoán, mức nền hoặc nhãn tham chiếu.

## Trò chuyện về lỗi

Khung trò chuyện có bản tin các cảnh báo gần đây, bộ chọn cảnh báo và những
câu hỏi gợi ý. Ví dụ:

- “Vì sao cảnh báo này nghiêm trọng?”
- “Chỉ số nào đang lệch nền và lệch bao nhiêu?”
- “Tôi cần kiểm tra gì trước?”
- “Tóm tắt tình trạng nguồn giám sát.”

Bot dùng thời điểm, năm chỉ số, mức nền, độ lệch, số phiếu và tên các thuật
toán làm chứng cứ. Câu trả lời ghi mã cảnh báo để đối chiếu. Trạng thái nguồn
đã dừng/mất tín hiệu được phân biệt với các cảnh báo trong lịch sử. Những
nguyên nhân có thể xảy ra là gợi ý điều tra, không phải nguyên nhân đã được
chứng minh. Bot không tự chạy SQL, tạo tải hoặc thay tham số mô hình.

Trong tab **Cấu hình AI**, bật AI, nhập API key OpenAI và model được tài
khoản của bạn hỗ trợ. Model mặc định là `gpt-6.2-sol`, có thể đổi trong biểu
mẫu. Khóa nhập ở ô mật khẩu, không nhập vào câu hỏi chat. Cấu hình và khóa
được giữ trong bộ nhớ Backend; sau khi Backend khởi động lại cần nhập lại,
trừ khi đã cấu hình biến môi trường.

Khi chưa có khóa hoặc dịch vụ AI không phản hồi, ứng dụng trả bản giải thích
có nhãn **theo quy tắc** từ số liệu đã lưu. Nó không được hiển thị như một
câu trả lời thành công từ mô hình AI. Tối đa tám lượt hỏi/đáp gần nhất được
lưu trong SQLite; mã cuộc trò chuyện được giữ trong phiên giao diện.

Phần AI gọi [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
với `store: false`, không cấp công cụ thực thi cho mô hình. Dữ liệu gửi ra
ngoài gồm câu hỏi, lịch sử chat giới hạn và chứng cứ chỉ số cần thiết; không
gửi mật khẩu CSDL, khóa SMTP hoặc ghi chú phản hồi DBA. Thông số `store` không
thay thế chính sách xử lý dữ liệu của nhà cung cấp API. Model tham chiếu:
[GPT-6.2 Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol).

## Gửi cảnh báo qua email

Trong tab **Email cảnh báo**, nhập:

- Máy chủ SMTP, cổng và kiểu bảo mật `starttls` hoặc `ssl`.
- Tài khoản gửi, mật khẩu SMTP hoặc mật khẩu ứng dụng.
- Địa chỉ người gửi và danh sách người nhận.
- Khoảng cách giữa các thông báo, mặc định **300 giây**.

Bật gửi email và lưu cấu hình. Có thể **Xem trước email** bằng một cảnh báo
đã lưu trước khi dùng **Gửi email kiểm tra**. Nút kiểm tra chỉ gửi thông báo
kiểm tra có nhãn rõ ràng đến danh sách người nhận đã cấu hình.

Với Gmail, cấu hình thường dùng `smtp.gmail.com`, cổng `587`, `starttls`;
hoặc cổng `465` với `ssl`. Tài khoản cần phương thức xác thực SMTP mà Google
cho phép, chẳng hạn mật khẩu ứng dụng khi tài khoản đủ điều kiện. Không dùng
mã OTP làm mật khẩu SMTP. Xem [cấu hình SMTP Gmail](https://developers.google.com/workspace/gmail/imap/imap-smtp)
và [mật khẩu ứng dụng](https://support.google.com/accounts/answer/185833).
Ứng dụng hiện dùng xác thực SMTP tài khoản/mật khẩu; chưa triển khai OAuth2.

Email được xếp hàng cho **mẫu mới có ít nhất 2/4 phiếu sau lọc vận hành**.
Một phiếu chỉ ghi nhật ký theo dõi. Bật email không tự gửi lại toàn bộ lịch
sử cũ. Các mẫu cùng nguồn, phiên nền, phiên thu và mức cảnh báo được giới
hạn thông báo theo khoảng chờ; nâng mức từ cảnh báo lên nghiêm trọng có thể
gửi riêng. Nhờ đó 15 mẫu sự cố liên tiếp không tạo 15 email giống nhau.

Thông báo có thời điểm, nguồn, mã mẫu, số phiếu, thuật toán bỏ phiếu, năm
chỉ số, độ lệch nền và hướng kiểm tra. Dữ liệu K1–K4 được đánh dấu **mô phỏng**.
Nội dung email tạo trực tiếp từ số liệu, không phụ thuộc API AI hoạt động.

Tiến trình gửi chạy ở Backend, độc lập tab trình duyệt và không chặn bộ thu.
Hàng đợi và trạng thái gửi được lưu trong SQLite. **SMTP đã nhận** chỉ có
nghĩa máy chủ gửi chấp nhận thư, không xác nhận thư đã vào Inbox hoặc được
đọc. Khi gửi lỗi/không xác định, giao diện hiển thị đúng trạng thái. Tác vụ
đang gửi khi dịch vụ khởi động lại được đánh dấu không xác định, không tự
gửi trùng. Có thể kiểm tra lại cấu hình và dùng email kiểm tra sau khi sửa.

Mật khẩu SMTP không lưu vào SQLite hoặc báo cáo. Có thể tắt gửi tự động
trong biểu mẫu mà vẫn giữ lịch sử. Bản ứng dụng này chạy cục bộ theo README;
các biểu mẫu cấu hình không thay thế cơ chế đăng nhập/phân quyền khi triển
khai cho nhiều người dùng.

## Cấu hình bằng biến môi trường

Ngoài biểu mẫu, Backend hỗ trợ `OPENAI_API_KEY`, `OPENAI_MODEL`,
`ANOMALY_AI_ENABLED`, `ANOMALY_EMAIL_ENABLED`, `SMTP_HOST`, `SMTP_PORT`,
`SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAIL_TO`
và `ALERT_EMAIL_COOLDOWN_SECONDS`. Nhập bí mật vào môi trường riêng của
Backend, không ghi khóa thật vào repository. Các thay đổi môi trường chỉ
áp dụng khi Backend khởi động với cấu hình đó.

## API bổ sung

Tất cả nằm dưới `/monitor/assistant`:

| API | Vai trò |
|---|---|
| `GET /status` | Trạng thái AI và email, không trả khóa/mật khẩu |
| `GET /briefing` | Bản tin từ cảnh báo gần đây và trạng thái nguồn |
| `POST /chat` | Hỏi về cảnh báo, nhận câu trả lời và mã chứng cứ |
| `GET /history` | Đọc lịch sử theo mã cuộc trò chuyện |
| `POST /config/ai` | Bật/tắt, cấu hình khóa API và model trong bộ nhớ |
| `POST /config/email` | Bật/tắt, cấu hình SMTP và người nhận |
| `GET /email/preview` | Xem trước nội dung từ mã cảnh báo |
| `POST /email/test` | Xếp hàng một email kiểm tra được yêu cầu rõ ràng |

Các kiểm thử dùng API/SMTP giả lập; không cần khóa AI hoặc gửi email thật
khi chạy `python -m unittest discover -s tests -q`.

# vi-media-kit

Bộ thư viện Python nhỏ cho ứng dụng giọng nói và phụ đề tiếng Việt. Không có giao diện, không kèm model, không kèm ffmpeg.
Toàn bộ mã trong repo này là mã viết mới; repo không chứa mã, dữ liệu, biểu tượng hay tệp thực thi của ứng dụng bên thứ ba.

Thông báo cho người dùng viết bằng tiếng Việt, tên hàm và biến phần lớn cũng là tiếng Việt không dấu.

## Có gì bên trong

| Mô-đun | Việc làm |
|---|---|
| `vimediakit.srt` | Đọc/ghi `.srt`: chịu CRLF, thiếu số thứ tự, mốc `.` thay `,` |
| `vimediakit.subtitles` | Xuất `srt/vtt/txt`, gộp/tách câu, đọc đúng mã hoá (UTF-8, UTF-16, cp1258), tìm không dấu |
| `vimediakit.dubbing` | Lồng tiếng thử nghiệm: mỗi câu phụ đề → TTS (hàm do bạn truyền vào) → ghép đúng mốc, tự tăng tốc khi câu dài (cần ffmpeg) |
| `vimediakit.render_min` | Ghi cứng phụ đề vào video và/hoặc thay âm thanh, có tiến trình và huỷ (cần ffmpeg) |
| `vimediakit.modeldl` | Tải model faster-whisper từ Hugging Face: nối tiếp khi đứt, kiểm sha256, báo tiến trình, huỷ được |
| `vimediakit.hwprofile` | Dò CPU/RAM/GPU NVIDIA và gợi ý model, số luồng, beam |
| `vimediakit.diagnostics` | Gói chẩn đoán dạng zip, tự che giá trị nhạy cảm (key, token, mật khẩu) |
| `vimediakit.errors` | Đổi ngoại lệ kỹ thuật thành câu tiếng Việt dễ hiểu |
| `vimediakit.netmode` | Chế độ offline (biến môi trường `VIMEDIA_OFFLINE=1`) |
| `vimediakit.history`, `applog`, `procutil`, `mediainfo` | Lịch sử ghi nguyên tử, log xoay vòng + crash log, chạy tiến trình không nháy console, đọc kích thước/thời lượng video không cần ffprobe |
| `vimediakit.jobs`, `theme` | Tác vụ nền huỷ được cho PySide6 và bảng màu sáng/tối (cần `PySide6`) |

## Cài và chạy thử

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip
python -m pytest                                  # chạy hoàn toàn offline
```

Các test dùng ffmpeg sẽ tự bỏ qua nếu máy không có ffmpeg trong PATH.

## Ví dụ

```python
from vimediakit import subtitles

cues = subtitles.doc("phu_de.srt")
subtitles.ghi(cues, "phu_de.vtt")
```

## Giấy phép và thành phần bên thứ ba

Mã trong repo theo giấy phép [MIT](LICENSE) (bản quyền thuộc tác giả `anhtahaylove`), cung cấp nguyên trạng, không bảo hành.

Repo **không đóng gói** bất kỳ thành phần bên thứ ba nào; những thứ bạn tự cài hoặc tải thêm có giấy phép riêng của chúng:

- **ffmpeg**: chương trình riêng, bạn tự cài. Tuỳ bản dựng, ffmpeg có thể theo GPL/LGPL; hãy xem giấy phép của bản bạn dùng trước khi phân phối lại cùng ffmpeg.
- **Model Whisper**: `modeldl` chỉ tải từ Hugging Face khi bạn gọi nó; mỗi model có giấy phép riêng ghi trên trang kho model đó.
- **PySide6** (tuỳ chọn, cho `jobs`, `theme`): LGPL/thương mại của The Qt Company. **numpy, soundfile, psutil**: giấy phép BSD.

## Đóng góp

Xem [CONTRIBUTING.md](CONTRIBUTING.md). Lịch sử thay đổi ở [CHANGELOG.md](CHANGELOG.md).

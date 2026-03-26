# Tiêu chuẩn Phát triển Frontend (FE Dev Standards) — Knowledge Platform

Bộ tri thức này định nghĩa các quy tắc và phong cách lập trình Frontend tại Knowledge Platform, hướng tới trải nghiệm người dùng (UX) mượt mà và mã nguồn (Code) dễ bảo trì.

## 1. Kiến trúc Thành phần (Component Architecture)
- **Atomic Design**: Chia nhỏ component thành các phần tử nguyên tử (atoms, molecules, organisms) để tái sử dụng tối đa.
- **Dumb & Smart Components**: Tách biệt logic nghiệp vụ (Smart/Container) khỏi giao diện hiển thị (Dumb/Presentational).
- **Props Validation**: Luôn định nghĩa rõ kiểu dữ liệu cho Props (TypeScript Interfaces).

## 2. Quản lý Trạng thái (State Management)
- **Local State**: Ưu tiên sử dụng `useState` cho các logic cục bộ (ví dụ: đóng/mở modal).
- **Global State**: Sử dụng Context API hoặc các thư viện nhẹ (Zustand/Signals) cho các dữ liệu dùng chung toàn app (User info, Theme).
- **Optimistic Updates**: Cập nhật UI ngay lập tức trước khi nhận phản hồi từ API để tăng cảm giác tốc độ.

## 3. Styling & UX Excellence
- **Vanilla CSS / Modern CSS**: Ưu tiên sử dụng CSS variables, Flexbox và Grid. Tránh inline styles.
- **Glassmorphism & Gradients**: Sử dụng các hiệu ứng hiện đại, mờ đục và gradient mượt mà để tạo cảm giác "Premium".
- **Micro-animations**: Thêm các hiệu ứng chuyển cảnh nhỏ (hover, transition) để làm giao diện sinh động.

## 4. Hiệu năng & Tối ưu (Performance)
- **Lazy Loading**: Sử dụng `React.lazy` và `Suspense` cho các route hoặc component lớn.
- **Image Optimization**: Luôn sử dụng đúng định dạng (WebP) và kỹ thuật lazy-load cho hình ảnh.
- **A11y (Accessibility)**: Đảm bảo khả năng điều hướng bằng bàn phím và hỗ trợ Screen Reader (ARIA labels).

## 5. Xử lý Lỗi & Logging
- **Error Boundaries**: Cài đặt Error Boundary ở cấp độ module để tránh làm sập toàn bộ ứng dụng.
- **Toast/Modal Notifications**: Thông báo lỗi rõ ràng, thân thiện với người dùng (không hiện mã lỗi kỹ thuật thuần túy).

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent*

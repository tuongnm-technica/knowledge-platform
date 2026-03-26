# Khung thực thi Phát triển Frontend (FE Execution Spec - Hardened)

Bộ quy tắc này ép buộc tính đồng bộ và chất lượng UX/UI cấp độ Premium cho mọi sản phẩm thuộc Knowledge Platform.

## 1. Cấu trúc Thành phần & Logic layer (Enforced)
- **Folder Structure**: Bắt buộc tuân thủ Atomic Design: `components/atoms/`, `components/molecules/`, `components/organisms/`, `components/templates/`.
- **Logic Layer (Custom Hooks)**: 100% logic nghiệp vụ/gọi API phải nằm trong Custom Hooks (`hooks/`). Component chỉ được chứa logic hiển thị.
- **Dumb Components**: Không được phép chứa bất kỳ Side-effect (`useEffect`) hoặc API call nào.

## 2. Quản lý Trạng thái & Data fetching (Spec)
- **Global State**: Sử dụng **Zustand** cho các trạng thái nhẹ, dùng chung (Auth, Theme). 
- **Server State**: Bắt buộc dùng **React Query** (hoặc SWR). 
  - `staleTime`: Mặc định 5 phút.
  - `retry`: Mặc định 3 lần cho lỗi mạng.
- **Form State**: Sử dụng **React Hook Form** kết hợp với **Zod** để validate schema ngay tại client.

## 3. Styling & UX Premium Standard (Glassmorphism)
- **Styling**: Ưu tiên **TailwindCSS** cho các lớp tiện ích + **CSS Modules** cho các phong cách tùy chỉnh phức tạp.
- **Premium UI (Glassmorphism Spec)**:
  - `background`: `rgba(255, 255, 255, 0.05)` (Dark mode) hoặc `rgba(255, 255, 255, 0.7)` (Light mode).
  - `backdrop-filter`: `blur(12px) saturate(180%)`.
  - `border`: `1px solid rgba(255, 255, 255, 0.125)`.
- **Typography**: Chỉ sử dụng font **Inter** hoặc **Outfit**. Font-size tối thiểu cho text là `14px`.

## 4. Hiệu năng & Khả năng tiếp cận (Optimization)
- **Lazy Loading**: 100% Routes phải được bọc trong `React.lazy` và `Suspense`.
- **Image handling**: Mặc định dùng định dạng **WebP**. Phải có thuộc tính `loading="lazy"` cho các ảnh dưới màn hình đầu tiên.
- **A11y Checklist**: 
  - Mọi interactive element (`button`, `a`) phải có `aria-label` nếu không có text hiển thị.
  - Độ tương phản màu sắc (Contrast ratio) tối thiểu đạt **4.5:1** (tiêu chuẩn WCAG AA).

## 5. Resilience & Observability (FE)
- **Error Boundaries**: Bọc từng module chức năng lớn (ví dụ: Chat, Dashboard) trong một Error Boundary riêng.
- **Logging**: Phát hiện lỗi Render và gửi log trực tiếp về **Sentry** (hoặc hệ thống Log tập trung) kèm theo `trace_id`.
- **Feedback Loop**: Luôn hiển thị trạng thái `Loading` (Skeleton screen) và thông báo `Success/Error` qua Toast notification.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (FE Execution-ready)*

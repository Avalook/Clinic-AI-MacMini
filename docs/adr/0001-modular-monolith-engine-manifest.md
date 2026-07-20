# ADR-0001 — Modular monolith với ENGINE + module manifest (không microservices, không event-driven single-writer)

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-18 |
| **Deciders** | Quang |
| **Liên quan** | Design doc v5 §5.2–5.3 |
| **Affected decisions (canon 06)** | Supersedes: D006 + A-9 (Golden Record single-writer qua event bus), kiến trúc tầng 0A–0C của final_canon 00 §5.1. Giữ nguyên intent: "một bảng một writer" — chuyển từ single-writer-process sang **single-writer-module** enforce bằng manifest + CI checker |

## Context
Peak traffic ~1 RPS, 1 team, 1 node Mac mini. Nhu cầu thật là **ranh giới nghiệp vụ rõ**
(8 module + engine + sổ cái) để thêm tính năng không đục code cũ — không phải scale
độc lập từng phần. Canon 2026-05 vẽ event-driven RabbitMQ + Golden Record single-writer,
nhưng 14 tháng thực tế cho thấy: dashboard ghi thẳng Supabase, RabbitMQ chưa từng chạy,
và mô hình đó tốn vận hành mà không giải bài toán nào đang có.

## Decision
Chúng ta dùng **modular monolith**: 1 FastAPI + 1 Postgres; module = thư mục
(`engine/`, `modules/<x>/`, `ledgers/`, `platform/`, `integrations/`) với **manifest 7
mục** (owns_tables, api, nodes, form_schema, events, provides/consumes, permissions).
Ranh giới enforce bằng CI: import-linter chặn import chéo + checker "mỗi bảng đúng 1
module writer" đọc manifest. Engine không biết nghiệp vụ; module không ghi chéo; bề mặt
generic.

## Considered Options
| Phương án | Ưu | Nhược |
|---|---|---|
| **A (chọn) Modular monolith + manifest + CI checker** | 90% lợi ích ranh giới, ~5% chi phí; transaction đa bảng dễ; 1 deploy | kỷ luật phụ thuộc CI checker |
| B Microservices theo module | ranh giới cứng bằng hạ tầng | ops ×10, saga/2PC cho luồng khám, vô nghĩa ở 1 RPS |
| C Event-driven single-writer (canon cũ) | audit đẹp, decouple | RabbitMQ + Golden Record = 2 mảnh chưa từng chạy; độ trễ ghi; phức tạp không mua được gì |

## Consequences
**Tích cực:** thêm nghiệp vụ = thêm module; lối thoát microservices sau này đi đúng theo
ranh giới manifest nếu có bằng chứng (>500 BN/ngày, đa cơ sở). **Tiêu cực:** phải xây
checker + giữ kỷ luật manifest; refactor code hiện tại về đúng thư mục là việc thật
(4 đợt trong design doc §8).

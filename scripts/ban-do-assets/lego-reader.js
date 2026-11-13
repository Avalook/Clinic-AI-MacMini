/* A reading view over the original LEGO data; the source map stays available. */
(function () {
  "use strict";
  const host = document.getElementById("lego-guide");
  const data = window.MAP_DATA && window.MAP_DATA.lego;
  if (!host || !data) return;

  const ops = data.thao_tac || [];
  const business = data.khoi_nghiep_vu || [];
  const infrastructure = data.khoi_ha_tang || [];
  const blocks = business.concat(infrastructure);
  const opById = Object.fromEntries(ops.map(op => [op.id, op]));
  const blockById = Object.fromEntries(blocks.map(block => [block.id, block]));
  const suggestions = data.de_xuat || [];
  const state = { mode: "nv", group: "all", query: "", op: opById["tiep-don-01"] ? "tiep-don-01" : (ops[0] || {}).id, step: 0, inspector: null, list: false };
  const names = {
    "trinh-duyet": ["Màn hình đang mở", "Trình duyệt"],
    caddy: ["Cửa vào an toàn", "Caddy · HTTPS"],
    next: ["Giao diện & chuyển lệnh", "Next.js"],
    gotrue: ["Kiểm tra đăng nhập", "GoTrue + auth-guard"],
    postgrest: ["Cổng đọc dữ liệu", "PostgREST"],
    api: ["Xử lý luật nghiệp vụ", "FastAPI"],
    postgres: ["Lưu và bảo vệ dữ liệu", "Postgres"],
    "su-kien": ["Giao việc sau sự kiện", "Worker su-kien"],
    sse: ["Báo tin cho các màn", "SSE"],
    "day-tep": ["Chuyển tệp kết quả", "Viettel CFS"],
    "sao-luu": ["Giữ bản sao dữ liệu", "Timer systemd"],
    "giam-sat": ["Theo dõi hệ thống", "Kuma · Dozzle · /ops"]
  };
  const configKeys = {
    api: ["uvicorn", "pool_min", "pool_api", "pool_staging", "sql_timeout", "identity_ttl", "tran_nguoi", "canh_pool", "api_ram"],
    next: ["next_tran", "next_tg", "dash_ram"], postgres: ["pg_image", "max_conn"],
    "su-kien": ["sukien_nghi", "pool_worker", "lan_thu", "han_thue", "sukien_ram"],
    sse: ["queue_sse", "nhip_sse", "noi_lai"], "trinh-duyet": ["gop_tin", "poll", "chuong_poll", "idem_ttl"],
    gotrue: ["gotrue_pool"], postgrest: ["pgrst_pool"], caddy: ["caddy_ram"],
    "sao-luu": ["sao_luu_15p", "sao_luu_dem", "staging_nap", "giu_15p"]
  };
  const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const list = value => Array.isArray(value) ? value : [];
  const fold = value => String(value || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");
  const unique = values => [...new Set(values)];
  const label = id => blockById[id] ? blockById[id].ten : id;
  const source = value => value ? '<p class="lx-source"><span>Nguồn</span><code>' + esc(value) + "</code></p>" : "";
  const codes = values => list(values).length ? '<div class="lx-codes">' + values.map(value => "<code>" + esc(value) + "</code>").join("") + "</div>" : '<p class="lx-muted">Nguồn chưa ghi mục nào.</p>';
  const bullet = values => list(values).length ? "<ul>" + values.map(value => "<li>" + esc(value) + "</li>").join("") + "</ul>" : '<p class="lx-muted">Nguồn chưa ghi mục nào.</p>';
  const timeLabel = value => value === "do" ? "Đã đo" : value === "uoc" ? "Ước theo code" : (value || "Chưa có nhãn đo");
  function readerActor(value) {
    const text = String(value || "");
    if (/^\(tự chạy\)/i.test(text)) return "Tác vụ tự động";
    if (/^lego\b/i.test(text)) return "Người được cấp quyền cho thao tác này";
    return text.replace(/\s*\((?:lego|quyền|cửa trang hỏi)[^)]*\)/gi, "").split(/\s*[—;]\s*/)[0].trim();
  }
  const dt = (term, description) => "<dt>" + esc(term) + "</dt><dd>" + (description || "Chưa ghi trong nguồn") + "</dd>";
  const disclosure = (title, content, open) => '<details class="lx-details"' + (open ? " open" : "") + "><summary>" + esc(title) + '</summary><div class="lx-details-body">' + content + "</div></details>";
  const opButton = op => '<button type="button" class="lx-text-link" data-lx-op="' + esc(op.id) + '">' + esc(op.ten) + "</button>";
  function canonicalTable(id) {
    if ((data.bang || {})[id]) return id;
    const match = String(id).match(/^([A-Za-z_][A-Za-z0-9_]*)\s+\(/);
    return match && (data.bang || {})[match[1]] ? match[1] : id;
  }
  const tableButton = id => '<button type="button" class="lx-table-link" data-lx-table="' + esc(canonicalTable(id)) + '"><code>' + esc(id) + "</code></button>";
  const tableButtons = ids => list(ids).length ? '<div class="lx-codes">' + ids.map(tableButton).join("") + "</div>" : '<p class="lx-muted">Không có bảng được liệt kê trong nguồn.</p>';
  const searchIndex = new Map(ops.map(op => [op.id, fold(JSON.stringify(op) + " " + list(op.qua).map(label).join(" ") + " " + list(op.ha_tang).map(label).join(" ") + " " + list(op.bang_ghi).concat(list(op.bang_doc)).map(id => (data.bang[id] || {}).nghia).join(" "))]));
  let lastInspectorTrigger = null;

  host.classList.add("lx-root");
  host.innerHTML = '<div class="lx-workspace"><aside class="lx-browser" aria-label="Danh sách thao tác"><div class="lx-browser-controls"><div class="lx-modes" role="group" aria-label="Lọc theo loại khối"><button type="button" data-lx-mode="nv" aria-pressed="true">Nghiệp vụ</button><button type="button" data-lx-mode="ht" aria-pressed="false">Hạ tầng</button></div><label class="lx-field" for="lx-group">Nhóm muốn xem<select id="lx-group"></select></label><label class="lx-field" for="lx-search">Tìm trong toàn bộ thao tác<input type="search" id="lx-search" autocomplete="off" placeholder="Ví dụ: thu tiền, check-in, payment…" aria-describedby="lx-search-help"></label><p class="lx-help" id="lx-search-help">Tìm được cả chữ không dấu, màn, API, bảng, sự kiện và tệp nguồn.</p><div class="lx-result-meta"><p id="lx-result-count" role="status" aria-live="polite"></p><button type="button" class="lx-text-link" id="lx-reset" hidden>Xoá bộ lọc</button></div></div><div id="lx-results"></div><details class="lx-block-directory"><summary>Xem các khối của nhóm này</summary><div id="lx-blocks"></div></details></aside><article class="lx-reader" aria-label="Giải thích thao tác"><div id="lx-operation"></div><section id="lx-inspector" class="lx-inspector" hidden aria-labelledby="lx-inspector-title"></section><div id="lx-story"></div><div id="lx-reference"></div></article></div>';

  function filteredOps() {
    const words = fold(state.query.trim()).split(/\s+/).filter(Boolean);
    return ops.filter(op => {
      const inGroup = state.group === "all" || (state.mode === "nv" ? list(op.qua).includes(state.group) || op.khoi === state.group : list(op.ha_tang).includes(state.group));
      return inGroup && words.every(word => searchIndex.get(op.id).includes(word));
    });
  }

  function renderControls() {
    const groups = state.mode === "nv" ? business : infrastructure;
    host.querySelectorAll("[data-lx-mode]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.lxMode === state.mode)));
    host.querySelector("#lx-group").innerHTML = '<option value="all">Tất cả ' + ops.length + " thao tác</option>" + groups.map(group => {
      const count = ops.filter(op => state.mode === "nv" ? list(op.qua).includes(group.id) || op.khoi === group.id : list(op.ha_tang).includes(group.id)).length;
      return '<option value="' + esc(group.id) + '"' + (state.group === group.id ? " selected" : "") + ">" + esc(group.ten) + " · " + count + "</option>";
    }).join("");
    host.querySelector("#lx-blocks").innerHTML = groups.map(group => '<button class="lx-directory-block" type="button" data-lx-block="' + esc(group.id) + '"><strong>' + esc(group.ten) + '</strong><span>' + esc(group.mo_ta) + "</span></button>").join("");
  }

  function renderResults() {
    const found = filteredOps();
    host.querySelector("#lx-result-count").textContent = found.length + " / " + ops.length + " thao tác";
    host.querySelector("#lx-reset").hidden = !(state.query || state.group !== "all");
    host.querySelector("#lx-results").innerHTML = found.length ? '<ol class="lx-results">' + found.map(op => '<li><button type="button" class="lx-result" data-lx-op="' + esc(op.id) + '"' + (state.op === op.id ? ' aria-current="true"' : "") + "><strong>" + esc(op.ten) + '</strong><span>' + esc(label(op.khoi)) + "</span><span>" + esc(op.man_ten || op.man || op.ai) + "</span></button></li>").join("") + '</ol><p class="lx-list-note">Một thao tác có thể đi qua nhiều nhóm.</p>' : '<div class="lx-empty"><strong>Chưa thấy thao tác phù hợp.</strong><p>Thử từ ngắn hơn như “thu”, “lịch”, “kết quả”, hoặc xoá bộ lọc để tìm lại trong ' + ops.length + ' thao tác.</p><button type="button" class="lx-button" data-lx-reset>Xem tất cả thao tác</button></div>';
    host.classList.toggle("lx-list-open", state.list);
  }

  function renderOperation() {
    const op = opById[state.op];
    if (!op) return;
    host.querySelector("#lx-operation").innerHTML = '<button type="button" class="lx-button lx-back-list" data-lx-list>← Trở về danh sách · ' + ops.length + ' thao tác</button><p class="lx-kicker">' + esc(label(op.khoi)) + '</p><h3 class="lx-op-title" tabindex="-1">' + esc(op.ten) + '</h3><dl class="lx-context">' + dt("Ai làm", esc(readerActor(op.ai))) + dt("Ở đâu", esc(op.man_ten || op.man || "Tác vụ tự động")) + '</dl><p class="lx-reading-hint">Bấm <strong>Sau →</strong> để đọc tiếp. Quyền và mã nguồn đầy đủ ở phần tra cứu bên dưới.</p>';
  }

  function blockChain(ids) {
    const valid = unique(list(ids)).filter(id => blockById[id]);
    if (!valid.length) return '<p class="lx-muted">Nguồn chưa gắn khối hạ tầng cho bước này.</p>';
    return '<ol class="lx-chain" aria-label="Các khối tham gia bước đang xem">' + valid.map(id => {
      const block = blockById[id], name = names[id] || [block.ten, "Khối nghiệp vụ"];
      return '<li><button type="button" class="lx-brick' + (infrastructure.some(item => item.id === id) ? " lx-infra" : "") + '" data-lx-block="' + esc(id) + '"><strong>' + esc(name[0]) + '</strong><span>' + esc(name[1]) + '</span><span class="lx-brick-hint">Bấm xem vai trò</span></button></li>';
    }).join("") + "</ol>";
  }

  function suggestionsFor(kind, id, step) {
    return suggestions.filter(item => item.gan && item.gan.loai === kind && item.gan.id === id && (step == null || item.gan.buoc === step));
  }

  function stepSuggestions(op, step) {
    const ids = list(op.buoc[step] && op.buoc[step].de_xuat);
    return suggestions.filter(item => ids.includes(item.id) || (item.gan && item.gan.loai === "thao_tac" && item.gan.id === op.id && item.gan.buoc === step));
  }

  function suggestionCards(items) {
    return items.map(item => '<div class="lx-proposal"><h5>' + esc(item.van_de) + '</h5><p class="lx-muted">' + (item.moi ? "Phát hiện mới · chưa kiểm chéo" : "Đề xuất trong nguồn · chưa thể coi là đã triển khai") + '</p><dl class="lx-data">' + dt("Vì sao", esc(item.vi_sao)) + dt("Hướng sửa", esc(item.sua)) + (item.viec != null ? dt("Việc liên quan", esc(item.viec)) : "") + dt("Mức trong nguồn", esc(item.muc)) + (list(item.pr).length ? dt("PR liên quan", list(item.pr).map(esc).join(" · ")) : "") + '</dl>' + source(item.nguon) + "</div>").join("");
  }

  function stepTitle(step) {
    const ids = list(step.lop);
    if (ids.includes("su-kien")) return "Những bên nhận tiếp tục làm việc";
    if (ids.includes("sse")) return "Tin đổi dữ liệu trở về các màn";
    if (ids.includes("api")) return "Máy kiểm luật và xử lý yêu cầu";
    if (ids.includes("postgres")) return "Dữ liệu được bảo vệ ở database";
    if (ids.includes("caddy") || ids.includes("next")) return "Yêu cầu đi qua các lớp hệ thống";
    if (ids.includes("trinh-duyet")) return "Phía màn hình người dùng";
    return "Theo dõi diễn biến của thao tác";
  }

  function renderStory() {
    const op = opById[state.op];
    if (!op) return;
    const steps = list(op.buoc), step = steps[state.step];
    if (!step) { host.querySelector("#lx-story").innerHTML = '<div class="lx-empty">Nguồn chưa có từng bước cho thao tác này. Xem phần tra cứu đầy đủ bên dưới.</div>'; return; }
    const stepDx = stepSuggestions(op, state.step);
    const status = step.den === "do" ? "Chậm theo nguồn" : step.den === "vang" ? "Cần để ý" : "Luồng thông thường";
    host.querySelector("#lx-story").innerHTML = '<section class="lx-story" tabindex="0" aria-label="Đọc từng bước; phím trái và phải để đổi bước"><div class="lx-step-top"><p class="lx-kicker" role="status" aria-live="polite">BƯỚC ' + (state.step + 1) + ' / ' + steps.length + '</p><span class="lx-status lx-status-' + esc(step.den || "xanh") + '">' + esc(status) + '</span></div><div class="lx-progress" role="progressbar" aria-label="Tiến độ câu chuyện" aria-valuemin="1" aria-valuemax="' + steps.length + '" aria-valuenow="' + (state.step + 1) + '"><span style="width:' + (100 * (state.step + 1) / steps.length) + '%"></span></div><h4 class="lx-step-title">' + esc(stepTitle(step)) + '</h4><p class="lx-step-narrative">' + esc(step.y) + '</p>' + blockChain(step.lop) + (step.chi_tiet ? '<p class="lx-step-detail">' + esc(step.chi_tiet) + '</p>' : "") + (step.thoi_gian ? '<p class="lx-time"><strong>' + esc(step.thoi_gian) + '</strong><span>' + esc(timeLabel(step.nhan_tg)) + '</span></p>' : "") + (step.vi_sao_den ? '<div class="lx-notice"><strong>Vì sao cần để ý</strong><p>' + esc(step.vi_sao_den) + '</p></div>' : "") + (step.nguon ? disclosure("File và dòng của bước này", source(step.nguon)) : "") + (stepDx.length ? disclosure("Đề xuất gắn với bước này · " + stepDx.length, suggestionCards(stepDx)) : "") + '<div class="lx-step-controls"><button type="button" class="lx-button" data-lx-step="' + (state.step - 1) + '"' + (state.step === 0 ? " disabled" : "") + '>← Trước</button><span>' + (state.step === steps.length - 1 ? "Đã tới bước cuối" : 'Còn ' + (steps.length - state.step - 1) + ' bước') + '</span><button type="button" class="lx-button lx-primary" data-lx-step="' + (state.step + 1) + '"' + (state.step === steps.length - 1 ? " disabled" : "") + '>Sau →</button></div><p class="lx-help lx-key-hint">Có thể dùng phím ← / → khi đang ở khung này.</p></section>' + disclosure("Xem mục lục toàn bộ " + steps.length + " bước", '<ol class="lx-step-index">' + steps.map((item, index) => '<li><button type="button" data-lx-step="' + index + '"' + (state.step === index ? ' aria-current="step"' : "") + '><span class="lx-index-number">' + (index + 1) + '</span><span>' + esc(item.y) + '</span></button></li>').join("") + "</ol>");
  }

  function consumerInfo(id) {
    const consumer = (data.consumer || {})[id];
    if (!consumer) return '<li><code>' + esc(id) + '</code> · Nguồn chưa ghi mô tả.</li>';
    return '<li><strong>' + esc(consumer.ten || id) + '</strong><p>' + esc(consumer.viec) + '</p><dl class="lx-data">' + dt("Khối nhận", esc(label(consumer.khoi))) + dt("Hàm xử lý", "<code>" + esc(consumer.ham || id) + "</code>") + (consumer.tep ? dt("Tệp", "<code>" + esc(consumer.tep) + "</code>") : "") + dt("Bảng ghi tiếp", tableButtons(consumer.bang_ghi)) + '</dl>' + source(consumer.nguon) + '</li>';
  }

  function eventInfo(id) {
    const event = (data.su_kien || {})[id];
    if (!event) {
      const known = unique(String(id).match(/[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*/g) || []).filter(key => (data.su_kien || {})[key]);
      return '<li><code>' + esc(id) + '</code>' + (known.length ? '<ul class="lx-full-list">' + known.map(eventInfo).join("") + '</ul>' : '<p class="lx-muted">Nguồn chưa có mục mô tả riêng cho dòng sự kiện này.</p>') + '</li>';
    }
    return '<li><code>' + esc(id) + '</code>' + (event ? '<p>' + esc(event.nhan) + '</p><dl class="lx-data">' + dt("Module", esc(event.module)) + dt("Bên nhận trong danh mục", list(event.consumers).map(consumer => esc(((data.consumer || {})[consumer] || {}).ten || consumer)).join(" · ")) + '</dl>' + source(event.nguon) : "") + '</li>';
  }

  function edgeList(edges) {
    if (!list(edges).length) return '<p class="lx-muted">Không có dây nối được liệt kê.</p>';
    const wireNames = { goi: "gọi", bang: "đọc/ghi bảng", "su-kien": "tin/sự kiện" };
    return '<ul class="lx-edges">' + edges.map(edge => '<li><strong>' + esc(label(edge[0])) + '</strong><span> → ' + esc(wireNames[edge[2]] || edge[2]) + ' → </span><strong>' + esc(label(edge[1])) + '</strong></li>').join("") + '</ul>';
  }

  function renderReference() {
    const op = opById[state.op];
    if (!op) return;
    const opDx = suggestionsFor("thao_tac", op.id);
    const totals = [op.tong, op.tong_thoi_gian].filter((total, index, all) => total && all.findIndex(item => item && JSON.stringify(item) === JSON.stringify(total)) === index);
    let html = '<section class="lx-reference"><p class="lx-kicker">TRA CỨU ĐẦY ĐỦ</p><h4>Muốn đào sâu phần nào?</h4><p class="lx-muted">Mở đúng mục bạn cần. Tên kỹ thuật và nguồn được giữ nguyên để đối chiếu.</p>';
    html += disclosure("1. Màn hình, nút bấm, API và hàm dịch vụ", '<dl class="lx-data">' + dt("Mã thao tác", "<code>" + esc(op.id) + "</code>") + dt("Ai làm", esc(op.ai)) + dt("Tên màn", esc(op.man_ten)) + dt("Đường dẫn màn", "<code>" + esc(op.man) + "</code>") + dt("Nút / cách kích hoạt", esc(op.nut) + source(op.nut_nguon)) + dt("Lệnh API", op.api ? "<code>" + esc(op.api) + "</code>" : "Không có lệnh API được ghi trong nguồn") + dt("Router", op.router ? "<code>" + esc(op.router) + "</code>" : "Chưa ghi trong nguồn") + '</dl><h5>Hàm dịch vụ</h5>' + (list(op.dich_vu).length ? '<ul class="lx-full-list">' + op.dich_vu.map(service => '<li><code>' + esc(service.ten) + '</code>' + source(service.nguon) + '</li>').join("") + '</ul>' : '<p class="lx-muted">Không có hàm được liệt kê.</p>'));
    html += disclosure("2. Dữ liệu được đọc và ghi", '<h5>Bảng được ghi · ' + list(op.bang_ghi).length + '</h5>' + tableButtons(op.bang_ghi) + '<h5>Bảng được đọc khi xử lý lệnh · ' + list(op.bang_doc).length + '</h5>' + tableButtons(op.bang_doc) + '<h5>Bảng màn đọc khi tải dữ liệu · ' + list(op.bang_doc_man).length + '</h5>' + tableButtons(op.bang_doc_man) + '<p class="lx-help">Bấm tên bảng để xem nghĩa, tin thay đổi và mọi thao tác đọc/ghi bảng đó. Điều kiện đi kèm tên bảng vẫn được giữ nguyên.</p>');
    html += disclosure("3. Sự kiện, bên nhận và màn tự cập nhật", '<h5>Sự kiện nghiệp vụ · ' + list(op.su_kien).length + '</h5>' + (list(op.su_kien).length ? '<ul class="lx-full-list">' + op.su_kien.map(eventInfo).join("") + '</ul>' : '<p class="lx-muted">Nguồn không liệt kê sự kiện nghiệp vụ.</p>') + '<h5>Nhật ký khác</h5>' + codes(op.nhat_ky) + '<h5>Bên nhận thực hiện tiếp · ' + list(op.consumers).length + '</h5>' + (list(op.consumers).length ? '<ul class="lx-full-list">' + op.consumers.map(consumerInfo).join("") + '</ul>' : '<p class="lx-muted">Nguồn không liệt kê bên nhận.</p>') + '<h5>Màn tự cập nhật</h5>' + codes(op.man_tu_cap_nhat));
    html += disclosure("4. Giao dịch, chống trùng và thời gian", '<dl class="lx-data">' + dt("Giao dịch", esc(op.giao_dich)) + dt("Chống trùng", esc(op.khoa)) + dt("Số câu SQL", esc(op.so_sql) + ' <span class="lx-muted">· Ước theo code</span>') + (op.sau_khi_ghi ? dt("Màn làm gì khi ghi xong", esc(op.sau_khi_ghi)) : "") + totals.map(total => dt("Tổng thời gian", esc(total.y) + '<p class="lx-help">Tổng kết theo nguồn · xem riêng nhãn đo / ước trong từng bước.</p>')).join("") + '</dl>');
    html += disclosure("5. Chuỗi sự kiện theo thời gian", list(op.chuoi).length ? '<ol class="lx-timeline">' + op.chuoi.map(item => '<li><strong>' + esc(item.t) + '</strong><p>' + esc(item.y) + '</p></li>').join("") + '</ol>' : '<p class="lx-muted">Nguồn chưa ghi chuỗi mốc thời gian riêng cho thao tác này; các bước ở trên vẫn được giữ đầy đủ.</p>');
    html += disclosure("6. Tất cả khối và dây nối của thao tác", '<h5>Khối nghiệp vụ tham gia</h5>' + blockChain(op.qua) + '<h5>Khối hạ tầng tham gia</h5>' + blockChain(op.ha_tang) + '<h5>Dây nghiệp vụ</h5>' + edgeList(op.day_nv) + '<h5>Dây hạ tầng</h5>' + edgeList(op.day_ht));
    html += disclosure("7. Luật, phát hiện và đề xuất trong nguồn", blockRules(blockById[op.khoi]) + '<h5>Phát hiện khi lần dây · chưa kiểm chéo</h5>' + bullet(op.phat_hien) + '<h5>Đề xuất gắn với thao tác · ' + opDx.length + '</h5>' + (opDx.length ? suggestionCards(opDx) : '<p class="lx-muted">Chưa có đề xuất riêng trong nguồn. Các khối tham gia có thể có đề xuất của chúng.</p>'));
    html += '<p class="lx-source"><span>Đường đi lấy từ</span>' + esc(op.nguon_goc || "Nguồn LEGO") + '</p></section>';
    host.querySelector("#lx-reference").innerHTML = html;
  }

  function blockRules(block) {
    if (!block || !list(block.nho).length) return '<p class="lx-muted">Nguồn chưa ghi luật riêng cho khối này.</p>';
    return '<h5>Luật phải nhớ · ' + esc(block.ten) + '</h5><ul class="lx-full-list">' + block.nho.map(rule => '<li><strong>' + esc(rule.y) + '</strong><p>Vì sao: ' + esc(rule.vi_sao) + '</p>' + source(rule.nguon) + '</li>').join("") + '</ul>';
  }

  function configValue(id) {
    const config = (data.cau_hinh || {})[id];
    return config ? config.gia_tri : "{" + id + "}";
  }

  function blockContent(id) {
    const block = blockById[id];
    if (!block) return "";
    const isBusiness = business.some(item => item.id === id);
    const related = ops.filter(op => isBusiness ? op.khoi === id || list(op.qua).includes(id) : list(op.ha_tang).includes(id));
    const ownedTables = Object.keys(data.bang || {}).filter(table => data.bang[table].chu === id);
    const keys = unique((configKeys[id] || []).concat(list(block.so).flatMap(value => Array.from(value.matchAll(/\{([^}]+)\}/g), match => match[1])))).filter(key => data.cau_hinh[key]);
    const blockDx = suggestions.filter(item => item.gan && ((item.gan.loai === (isBusiness ? "khoi" : "ha_tang") && item.gan.id === id) || (isBusiness && item.gan.loai === "thao_tac" && opById[item.gan.id] && opById[item.gan.id].khoi === id)));
    let html = '<p class="lx-kicker">' + (isBusiness ? "KHỐI NGHIỆP VỤ" : "KHỐI HẠ TẦNG") + '</p><h4 id="lx-inspector-title" tabindex="-1">' + esc(block.ten) + '</h4><p>' + esc(block.mo_ta) + '</p>';
    if (block.routes) html += '<h5>Mọi đường dẫn màn của khối</h5>' + codes(block.routes);
    if (block.so) html += '<h5>Đặc điểm và cấu hình ghi trong nguồn</h5>' + bullet(block.so.map(value => value.replace(/\{([^}]+)\}/g, (_, key) => configValue(key))));
    if (keys.length) html += disclosure("Đối chiếu cấu hình và file nguồn · " + keys.length, '<ul class="lx-full-list">' + keys.map(key => '<li><strong>' + esc(data.cau_hinh[key].y) + '</strong><p><code>' + esc(configValue(key)) + '</code></p>' + source(data.cau_hinh[key].nguon) + '</li>').join("") + '</ul>');
    if (isBusiness) html += blockRules(block) + '<h5>Bảng thuộc khối theo ước lượng của nguồn · ' + ownedTables.length + '</h5><p class="lx-help">“Chủ” ở đây được ước theo khối có nhiều thao tác ghi bảng nhất, chưa phải khai chủ bảng chính thức (#513).</p>' + tableButtons(ownedTables);
    html += '<h5>Tất cả thao tác đi qua khối · ' + related.length + '</h5><ul class="lx-related">' + related.map(op => '<li>' + opButton(op) + '<span class="lx-muted">' + esc(label(op.khoi)) + '</span></li>').join("") + '</ul>';
    html += disclosure("Đề xuất liên quan khối · " + blockDx.length, blockDx.length ? suggestionCards(blockDx) : '<p class="lx-muted">Nguồn chưa ghi đề xuất riêng.</p>');
    return html;
  }

  function tableContent(id) {
    const table = (data.bang || {})[id];
    if (!table) return '<h4 id="lx-inspector-title" tabindex="-1">' + esc(id) + '</h4><p>Bảng được nhắc trong thao tác, nguồn chưa có bản mô tả riêng.</p>';
    const tableDx = suggestionsFor("bang", id);
    const related = ids => list(ids).length ? '<ul class="lx-related">' + ids.map(opId => '<li>' + (opById[opId] ? opButton(opById[opId]) : '<code>' + esc(opId) + '</code>') + '</li>').join("") + '</ul>' : '<p class="lx-muted">Nguồn chưa ghi thao tác nào.</p>';
    return '<p class="lx-kicker">BẢNG DỮ LIỆU</p><h4 id="lx-inspector-title" tabindex="-1"><code>' + esc(id) + '</code></h4><p>' + esc(table.nghia || table.ghi_chu || "Nguồn chưa ghi nghĩa của bảng.") + '</p>' + (table.nghia && table.ghi_chu ? '<p>' + esc(table.ghi_chu) + '</p>' : "") + '<dl class="lx-data">' + dt("Trigger báo tin", table.trigger ? 'Có · <code>notify_row_change</code>' + source(table.trigger) : "Không được ghi trong nguồn; ghi bảng này không tự phát tin qua trigger đó") + dt("Trong LIVE_TABLES", table.live ? "Có · theo danh sách dùng chung của màn thường" : "Không") + dt("Khối chủ (ước)", esc(label(table.chu) || "Chưa xác định")) + '</dl><p class="lx-help">Khối chủ được ước theo số thao tác ghi bảng; chưa phải tuyên bố sở hữu chính thức.</p>' + (table.canh ? '<div class="lx-notice">' + esc(table.canh) + '</div>' : "") + '<h5>Màn nghe bảng này</h5>' + codes(table.man_nghe) + '<h5>Tất cả bên ghi · ' + list(table.ghi_boi).length + '</h5>' + related(table.ghi_boi) + '<h5>Tất cả bên đọc · ' + list(table.doc_boi).length + '</h5>' + related(table.doc_boi) + (tableDx.length ? disclosure("Đề xuất cho bảng · " + tableDx.length, suggestionCards(tableDx)) : "");
  }

  function renderInspector(focus) {
    const inspector = host.querySelector("#lx-inspector");
    inspector.hidden = !state.inspector;
    if (!state.inspector) { inspector.innerHTML = ""; return; }
    inspector.innerHTML = '<button type="button" class="lx-button lx-close-inspector" data-lx-close>Đóng phần giải thích ↑</button>' + (state.inspector.kind === "block" ? blockContent(state.inspector.id) : tableContent(state.inspector.id));
    if (focus) inspector.querySelector("#lx-inspector-title").focus({ preventScroll: true });
    if (focus) inspector.scrollIntoView({ behavior: "auto", block: "start" });
  }

  function setOperation(id, notify) {
    if (!opById[id]) return;
    const changed = state.op !== id;
    state.op = id; state.list = false; state.inspector = null;
    if (changed) state.step = 0;
    renderResults(); renderOperation(); renderStory(); renderReference(); renderInspector(false);
    if (notify && typeof window.navigate === "function") window.navigate("lego", "nv/" + id);
    if (notify) { const title = host.querySelector(".lx-op-title"); title.focus({ preventScroll: true }); title.scrollIntoView({ block: "start", behavior: "auto" }); }
  }

  function setStep(index, focusControls) {
    const op = opById[state.op];
    if (!op || index < 0 || index >= list(op.buoc).length) return;
    state.step = index; renderStory();
    if (focusControls) host.querySelector(".lx-story").focus({ preventScroll: true });
  }

  function openInspector(kind, id, trigger, notify) {
    lastInspectorTrigger = trigger || null;
    state.list = false; state.inspector = { kind, id }; renderResults(); renderInspector(true);
    if (notify && kind === "block" && typeof window.navigate === "function") window.navigate("lego", id);
  }

  function closeInspector(notify) {
    state.inspector = null; renderInspector(false);
    if (lastInspectorTrigger && lastInspectorTrigger.isConnected) lastInspectorTrigger.focus({ preventScroll: true });
    if (notify && typeof window.navigate === "function") window.navigate("lego", "nv/" + state.op);
  }

  function resetFilters() {
    state.query = ""; state.group = "all"; host.querySelector("#lx-search").value = "";
    renderControls(); renderResults(); host.querySelector("#lx-search").focus();
  }

  host.addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button || !host.contains(button)) return;
    if (button.hasAttribute("data-lx-op")) return setOperation(button.dataset.lxOp, true);
    if (button.hasAttribute("data-lx-mode")) { state.mode = button.dataset.lxMode; state.group = "all"; renderControls(); renderResults(); return; }
    if (button.hasAttribute("data-lx-block")) return openInspector("block", button.dataset.lxBlock, button, true);
    if (button.hasAttribute("data-lx-table")) return openInspector("table", button.dataset.lxTable, button, false);
    if (button.hasAttribute("data-lx-step")) return setStep(Number(button.dataset.lxStep), true);
    if (button.hasAttribute("data-lx-close")) return closeInspector(true);
    if (button.hasAttribute("data-lx-reset") || button.id === "lx-reset") return resetFilters();
    if (button.hasAttribute("data-lx-list")) { state.list = true; renderResults(); host.querySelector("#lx-search").focus({ preventScroll: true }); host.querySelector(".lx-browser").scrollIntoView({ block: "start" }); }
  });
  host.querySelector("#lx-search").addEventListener("input", event => { state.query = event.target.value; renderResults(); });
  host.querySelector("#lx-group").addEventListener("change", event => { state.group = event.target.value; renderResults(); });
  host.addEventListener("keydown", event => {
    if (event.key === "Escape" && state.inspector) { event.preventDefault(); closeInspector(true); return; }
    if (event.target.matches("input, select, textarea") || !event.target.closest(".lx-story")) return;
    if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const index = event.key === "Home" ? 0 : event.key === "End" ? list(opById[state.op].buoc).length - 1 : state.step + (event.key === "ArrowRight" ? 1 : -1);
      setStep(index, true);
    }
  });
  function applyRoute(target) {
    let value = String(target || "");
    try { value = decodeURIComponent(value); } catch (_) { /* Malformed pasted fragments remain literal. */ }
    const id = value.replace(/^(nv|ht)\//, "");
    if (opById[id]) { if (state.op !== id || state.inspector || state.list) setOperation(id, false); return; }
    if (blockById[id] && (!state.inspector || state.inspector.id !== id)) openInspector("block", id, null, false);
  }
  document.addEventListener("clinicai-route", event => { if (event.detail && event.detail.section === "lego") applyRoute(event.detail.target); });
  renderControls(); renderResults(); renderOperation(); renderStory(); renderReference();
  const initial = (window.location.hash || "").replace(/^#\/?/, "");
  if (initial.startsWith("lego/")) applyRoute(initial.slice(5));
})();

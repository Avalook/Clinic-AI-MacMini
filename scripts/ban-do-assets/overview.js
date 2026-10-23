(() => {
 'use strict';
 const data=window.MAP_DATA,L=data.lego,S=data.system,$=id=>document.getElementById(id);
 const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const plain=s=>String(s??'').replace(/\[([^\]]+)\]\([^)]*\)/g,'$1').replace(/[*`]/g,'');
 const number=n=>Number(n).toLocaleString('vi-VN');
 const reduced=matchMedia('(prefers-reduced-motion:reduce)');
 const payment=L.thao_tac.find(x=>x.id==='thu-ngan-01');
 const journey=['dat-lich','tiep-don','kham','phong-dv','thu-ngan','thuoc','check-out','ket-qua-cskh'].map(id=>L.khoi_nghiep_vu.find(k=>k.id===id));
 const chapterKeys=['journey','payment','events','load','prod','tasks'];
 const names={journey:'Một bệnh nhân đi qua những đâu?',payment:'Bấm “Thu” rồi chuyện gì xảy ra?',events:'Vì sao một lần ghi làm nhiều màn đổi?',load:'Nếu nhiều người cùng bấm thì sao?',prod:'Nhìn một ngày hoạt động thật',tasks:'Từ đường đi này, nên sửa gì trước?'};
 const descriptions={journey:'Đọc theo thứ tự một khách đi trong phòng khám. Chọn một chặng hoặc bấm Bước tiếp; bạn tự quyết định tốc độ đọc.',payment:'Cùng lần theo một thao tác thật ở quầy thu dịch vụ. Tiền đã ghi xong và màn hình đã cập nhật là hai mốc khác nhau.',events:'“Có dữ liệu mới” và “giao việc cho phần khác” là hai đường liên quan. Đường sự kiện chạy sau, có hàng chờ và có nhịp nghỉ.',load:'Kéo số người rồi nhìn chỗ nào bắt đầu phải chờ. Đây là mô hình ước từ cấu hình và phân tích code, chưa chạy thử tải.',prod:'Dữ liệu đã lưu từ prod, đo ngày 23/10/2026. Bấm một cột để đọc số của giờ đó; số request không phải số bệnh nhân.',tasks:'Mở từng việc để đọc ảnh hưởng, nguyên nhân và cách sửa. Thứ tự lấy nguyên từ báo cáo, không chấm lại mức ưu tiên.'};
 const paymentTitles=['Thu ngân bấm nút','Lệnh đi qua các cửa','Kiểm tra và khoá lượt','Ghi tiền vào sổ gốc','Báo dữ liệu vừa đổi','Giao việc cho bên khác','Các tab đọc dữ liệu mới','Nút Thu sẵn sàng tiếp'];
 const paymentShort=[
  'Nút khoá ngay và gắn mã chống ghi trùng. Nếu mạng chập chờn, gửi lại vẫn dùng mã của thao tác này.',
  'Cửa vào Caddy nhận lệnh. Next.js kiểm phiên đăng nhập và chuyển lệnh tới FastAPI, nơi xử lý nghiệp vụ.',
  'Máy chủ khoá lượt khám, kiểm tra biên nhận cũ và tính lại hoá đơn. Nếu hoá đơn đổi, máy báo để người thu xem lại.',
  'Lần thu và từng dòng tiền được ghi trong một giao dịch. Đây là mốc tiền đã vào sổ; cả lệnh ghi khoảng 0,13 giây đã đo.',
  'Khi giao dịch chốt, Postgres phát tin “bảng vừa đổi”. Tin không chứa toàn bộ dữ liệu bệnh nhân.',
  'Worker nhận sự kiện thu tiền, rồi giao lần lượt cho công nợ, đối tác, dòng thời gian, hành trình và sổ nợ. Mỗi bên có thể ghi tiếp và phát tin tiếp.',
  'Các tab nhận tin rồi tự đọc lại dữ liệu. Nhiều đợt tin làm màn tải lại nhiều lần; phần đọc này mới là chỗ chờ lâu.',
  'Nút Thu đang chờ cả khoảng hai lượt tải bảng. Tổng chờ khoảng 7 giây là ước từ hai lượt tải p95 khoảng 3,4 giây đã đo.'
 ];
 const layerName={ 'trinh-duyet':['Màn hình','Trình duyệt'],'caddy':['Cửa vào','Caddy'],'next':['Chuyển lệnh / vẽ trang','Next.js'],'gotrue':['Kiểm phiên đăng nhập','GoTrue'],'api':['Xử lý nghiệp vụ','FastAPI'],'postgres':['Sổ dữ liệu gốc','Postgres'],'sse':['Đường báo đổi dữ liệu','SSE'],'su-kien':['Người giao việc nền','Worker su-kien'] };
 let chapter='journey',step=0,playing=false,timer=0,elapsed=0,last=0,frame=0,hour=S.prod.gio_dinh.gio,people=0;
 function stop(){if(playing&&last)elapsed+=performance.now()-last;playing=false;clearTimeout(timer);cancelAnimationFrame(frame);last=0;const button=$('guide-play');if(button){button.textContent=reduced.matches?'Bản tĩnh':'Tự chạy';button.setAttribute('aria-pressed','false')}}
 function count(){return chapter==='journey'?journey.length:chapter==='payment'?payment.buoc.length:chapter==='events'?4:1}
 function heading(){return `<div class="guide-heading"><span class="eyebrow">CÂU HỎI ${chapterKeys.indexOf(chapter)+1} / 6</span><h2>${names[chapter]}</h2><p>${descriptions[chapter]}</p></div>`}
 function controls(){return `<div class="story-toolbar"><p><strong id="story-position"></strong><br><span class="metadata">${reduced.matches?'Đang bật giảm chuyển động: đọc bản tĩnh.':'Bấm từng bước hoặc bật tự chạy. Nhịp kể chuyện, không phải thời gian đã đo.'}</span></p><div class="story-tools">${['journey','payment','events'].includes(chapter)?'<button type="button" data-guide-prev>← Trước</button><button type="button" class="primary" data-guide-next>Bước tiếp →</button>':''}<button type="button" id="guide-play" aria-pressed="false" ${reduced.matches?'disabled':''}>${reduced.matches?'Bản tĩnh':'Tự chạy'}</button><button type="button" id="guide-reset">Về đầu</button></div></div>`}
 function brick(title,sub,active){return `<div class="story-brick${active?' active':''}"><small>${active?'● Đang ở đây':escape(sub)}</small><strong>${escape(title)}</strong></div>`}
 function stage(parts,async=false){return `<div class="story-stage${parts.length>3?' many':''}">${parts.map((p,i)=>`${i?'<span aria-hidden="true" class="story-arrow'+(async?' async':'')+'">→</span>':''}${brick(p[0],p[1],p[2])}`).join('')}</div>`}
 function source(text,more=''){return `<details class="guide-source"><summary>Mở tên code & nguồn đối chiếu</summary><div class="detail-inner">${more}<p><code>${escape(text)}</code></p></div></details>`}
 function pager(){return '<div class="step-pager"><button type="button" id="step-prev">← Bước trước</button><button type="button" id="step-next" class="primary">Bước tiếp →</button></div>'}
 function position(){const el=$('story-position');if(el)el.textContent=['load','prod'].includes(chapter)?'Bạn có thể thay số và xem lại':`Bước ${step+1} / ${count()}`;document.querySelectorAll('#step-prev,[data-guide-prev]').forEach(a=>a.disabled=step===0);document.querySelectorAll('#step-next,[data-guide-next]').forEach(b=>{b.disabled=step===count()-1;b.textContent=step===count()-1?'Đã tới bước cuối':'Bước tiếp →'})}
 function buttons(){
  $('guide-play')?.addEventListener('click',()=>{if(playing){stop()}else{playing=true;$('guide-play').textContent='Tạm dừng';$('guide-play').setAttribute('aria-pressed','true');if(step===count()-1&&count()>1){step=0;elapsed=0;drawStep()}if(['load','prod'].includes(chapter)&&elapsed>=1800)elapsed=0;schedule()}});
  $('guide-reset')?.addEventListener('click',()=>{stop();step=0;elapsed=0;drawStep();if(chapter==='load')drawLoad(1);if(chapter==='prod')drawChart(1)});
  document.querySelectorAll('#step-prev,[data-guide-prev]').forEach(b=>b.addEventListener('click',()=>setStep(step-1)));document.querySelectorAll('#step-next,[data-guide-next]').forEach(b=>b.addEventListener('click',()=>setStep(step+1)));
  document.querySelectorAll('[data-story-step]').forEach(b=>b.addEventListener('click',()=>setStep(Number(b.dataset.storyStep))));
  $('story-select')?.addEventListener('change',()=>setStep(Number($('story-select').value)));
 }
 function schedule(){
  if(!playing||reduced.matches)return;
  if(chapter==='load'||chapter==='prod'){
   const base=elapsed;last=performance.now();const draw=chapter==='load'?drawLoad:drawChart;
   const tick=now=>{if(!playing)return;const p=Math.min(1,(base+now-last)/1800);draw(p);if(p<1)frame=requestAnimationFrame(tick);else stop()};frame=requestAnimationFrame(tick);return;
  }
  const duration=chapter==='events'&&step===1?Number(L.cau_hinh.sukien_nghi.gia_tri)*1000:3200;
  last=performance.now();timer=setTimeout(()=>{if(step<count()-1){step++;elapsed=0;last=0;drawStep();schedule()}else stop()},Math.max(0,duration-elapsed));
  if(chapter==='events'&&step===1){const tick=now=>{if(!playing)return;const clock=$('worker-clock');if(clock)clock.textContent=Math.max(0,(duration-elapsed-(now-last))/1000).toFixed(1).replace('.',',')+' giây';frame=requestAnimationFrame(tick)};frame=requestAnimationFrame(tick)}
  elapsed=0;
 }
 function setStep(value){stop();step=Math.max(0,Math.min(count()-1,value));elapsed=0;drawStep()}
 function journeyDetail(){
  const k=journey[step],previous=journey[step-1],next=journey[step+1],ops=L.thao_tac.filter(o=>o.khoi===k.id);
  return stage([[previous?.ten||'Khách có nhu cầu','Vừa qua',false],[k.ten,'',true],[next?.ten||'Chăm sóc tiếp','Tiếp theo',false]])+
   `<span class="eyebrow">CHẶNG ${step+1}</span><h3>${escape(k.ten)}</h3><p class="story-explanation">${escape(k.mo_ta)}.</p>`+
   `<div class="story-note"><strong>Điều cần nhớ ở chặng này</strong><p>${escape(k.nho?.[0]?.y||'Chọn một thao tác bên dưới để xem chi tiết.')}</p></div>`+
   `<h4>Một số việc người dùng làm ở đây</h4><div class="operation-shortcuts">${ops.slice(0,3).map(o=>`<a href="#lego/nv/${escape(o.id)}">${escape(o.ten)} →</a>`).join('')}</div>`+
   `<details><summary>Đọc kỹ: ${ops.length} thao tác, các màn & quy tắc</summary><div class="detail-inner"><ul class="story-list">${(k.nho||[]).map(n=>`<li>${escape(n.y)}<p class="muted">Vì sao: ${escape(n.vi_sao)}</p><code>${escape(n.nguon)}</code></li>`).join('')}</ul><h4>Các màn hình</h4>${(k.routes||[]).map(r=>`<code>${escape(r)}</code>`).join(' · ')}<h4 style="margin-top:20px">Toàn bộ thao tác</h4><div class="operation-shortcuts">${ops.map(o=>`<a href="#lego/nv/${escape(o.id)}">${escape(o.ten)} →</a>`).join('')}</div></div></details>`;
 }
 function paymentDetail(){
  const b=payment.buoc[step],layers=b.lop.map(id=>layerName[id]||[id,id]);
  return stage(layers.map((x,i)=>[x[0],x[1],i===0]),step>=4)+
   `<div class="row"><span class="tag ${b.den==='do'?'red':b.den==='vang'?'yellow':'green'}">${b.den==='do'?'● Chỗ chậm':b.den==='vang'?'● Có độ trễ':'● Đường đi ổn'}</span><span class="tag">${escape(b.thoi_gian)} · ${b.nhan_tg==='do'?'đã đo':'ước theo nguồn'}</span></div>`+
   `<h3 style="margin-top:16px">${paymentTitles[step]}</h3><p class="story-explanation">${paymentShort[step]}</p>`+
   (b.vi_sao_den?`<div class="story-note"><strong>Vì sao cần chú ý?</strong><p>${escape(b.vi_sao_den)}</p></div>`:'')+
   `<details><summary>Đọc đầy đủ bước này</summary><div class="detail-inner"><p>${escape(b.y)}</p><p>${escape(b.chi_tiet)}</p><p>Các tầng liên quan: ${b.lop.map(id=>`<a href="#lego/${id}">${escape(layerName[id]?.[1]||id)}</a>`).join(' → ')}</p></div></details>`+
   source(b.nguon)+`<p class="metadata">Số 0,13 giây là cả lệnh ghi đã đo. Số ~7 giây là ước từ 2 lượt tải × p95 ~3,4 giây trong tài liệu 14–17/10. Tự chạy chỉ diễn giải từng bước, không dùng làm đồng hồ đo.</p>`;
 }
 function eventsDetail(){
  const names=['Ghi sự kiện vào sổ','Worker nghỉ giữa các vòng','Giao lần lượt cho bên nhận','Bên nhận ghi tiếp, màn nhận tin'];
  const prose=[
   'Lệnh thu tiền ghi sự kiện payment.service_collected. Sổ domain_event và hàng giao event_delivery nằm trong Postgres để phần nền có việc cần làm.',
   'Worker su-kien nghỉ 1 giây giữa các vòng quét. Tin mới đến trong lúc này phải chờ lượt tiếp. Đây là một nguyên nhân làm các đợt cập nhật cách nhau.',
   'Worker xử lý từng cặp sự kiện × bên nhận. Sau thu tiền có các bên nhận riêng: công nợ, đối tác, dòng thời gian, hành trình và sổ nợ.',
   'Bên nhận có thể ghi dữ liệu, tạo sự kiện mới và làm Postgres phát tin bảng đổi. FastAPI đưa tin qua SSE; từng tab nghe tin rồi đọc lại dữ liệu.'
  ];
  const layers=[['Sổ sự kiện','domain_event',step===0],['Người giao việc nền','su-kien',step===1||step===2],['Màn khác đổi dữ liệu','SSE',step===3]];
  return stage(layers,true)+`<h3>${names[step]}</h3><p class="story-explanation">${prose[step]}</p>`+
   (step===1?`<div class="story-note"><strong>Nhịp nghỉ theo code</strong><p id="worker-clock">${escape(L.cau_hinh.sukien_nghi.gia_tri)} giây</p><p>Chọn Tự chạy để nhìn một nhịp chờ. Thời gian xử lý các bên nhận chưa có số đo riêng ở đây.</p></div>`:'')+
   (step===2?`<ul class="story-list">${payment.consumers.map(c=>`<li><strong>${escape(L.consumer[c]?.ten||c)}</strong><p>${escape(L.consumer[c]?.viec)}</p></li>`).join('')}</ul>`:'')+
   `<details><summary>Đọc chuỗi sự kiện sau một lần Thu</summary><ul class="story-list">${payment.chuoi.map(c=>`<li><strong>${escape(c.t)}</strong> — ${escape(c.y)}</li>`).join('')}</ul></details>`+
   `<div class="story-note"><strong>Hai khái niệm dễ lẫn</strong><p><b>Sự kiện nghiệp vụ</b> là giao việc tiếp, ví dụ thu tiền xong cần xếp phòng. <b>Tin bảng đổi qua SSE</b> là nhắc màn đọc lại số mới. Tin chỉ mang tên bảng và phòng khám.</p></div>`+
   source(L.cau_hinh.sukien_nghi.nguon);
 }
 function drawStep(){
  document.querySelectorAll('[data-story-step]').forEach(b=>{if(Number(b.dataset.storyStep)===step)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current')});
  if($('story-select'))$('story-select').value=String(step);
  const box=$('story-detail');if(box)box.innerHTML=chapter==='journey'?journeyDetail():chapter==='payment'?paymentDetail():eventsDetail();position();
 }
 function drawLoad(progress=1){
  const n=[1,11,101,1000][people],pool=Number(L.cau_hinh.pool_api.gia_tri),next=Number(L.cau_hinh.next_tran.gia_tri),worker=1;
  $('load-value').textContent=number(n);$('load-range').setAttribute('aria-valuetext',number(n)+' người');
  document.querySelectorAll('[data-people]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.people)===people)));
  const rows=[['next','Máy dựng trang',next,'tiến trình',n],['pool','Bể kết nối API',pool,'kết nối',n],['postgres','Sổ dữ liệu gốc',S.db.max_ket_noi,'kết nối',Math.min(n,pool)],['su-kien','Người giao việc nền',worker,'tiến trình',n]];
  $('load-layers').innerHTML=rows.map(([id,title,cap,unit,demand])=>{const layer=L.tai.tang.find(t=>t.id===id);return `<article><span class="eyebrow">${escape(id==='next'?'Next.js':id==='pool'?'asyncpg':id==='postgres'?'Postgres':'su-kien')}</span><h3>${title}</h3><p><b>${cap}</b> ${unit} theo cấu hình</p><div class="queue-track" aria-hidden="true"><div class="queue-fill" style="width:${Math.min(demand/cap,1)*progress*100}%"></div></div><p>${id==='pool'?`Tối đa ${Math.min(n,pool)} lệnh đang mượn; ${number(Math.max(0,n-pool))} lệnh chờ (ước).`:id==='postgres'?`Riêng API đưa vào tối đa ${Math.min(n,pool)} kết nối; còn GoTrue, worker và các bên khác.`:id==='next'?`${number(n)} tab chia việc dựng trang trên ${cap} tiến trình.`:'Giao từng bên nhận lần lượt; hàng event_delivery lưu trên đĩa.'}</p><details><summary>Đọc phân tích ${number(n)} người</summary><p>${escape(n===1?'Một người: đối chiếu cấu hình, không có số thử tải riêng.':layer['n'+n])}</p><code>${escape(layer.nguon)}</code></details></article>`}).join('');
 }
 function load(){return controls()+`<div class="guide-range"><label for="load-range">Số người cùng bấm: <strong id="load-value"></strong></label><input type="range" min="0" max="3" step="1" value="${people}" id="load-range"><div class="range-stops">${[1,11,101,1000].map((n,i)=>`<button type="button" data-people="${i}">${number(n)}</button>`).join('')}</div></div><p class="metadata">Thanh tô biểu diễn mức dùng so với sức chứa, không phải thời gian hay số request đo thực tế.</p><div id="load-layers" class="guide-load"></div><div class="story-note"><strong>Nên nhìn chỗ nào trước?</strong><p>${escape(L.tai.co_chai)}</p></div><details><summary>Xem đầy đủ phân tích & an toàn khi bấm trùng</summary><p>${escape(L.tai.kich_ban)}</p><ul>${L.tai.an_toan.map(x=>`<li>${escape(x.y)}<p><code>${escape(x.nguon)}</code></p></li>`).join('')}</ul><a href="#lego/goc/tai">Mở chế độ 1.000 người đầy đủ →</a></details>`}
 function drawChart(progress=1){document.querySelectorAll('.hours-chart i').forEach((el,i)=>el.style.transform=`scaleY(${Math.min(1,Math.max(0,progress*2-i/24))})`)}
 function selectHour(n){hour=n;document.querySelectorAll('[data-hour]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.hour)===hour)));$('hour-value').innerHTML=`<strong>${hour}h–${hour+1}h: ${number(S.prod.req_moi_gio[hour])} request</strong><br><span class="metadata">${hour===S.prod.gio_dinh.gio?'Giờ có nhiều request nhất trong cửa sổ đo.':'Đã đo trong cửa sổ 24 giờ. Bấm cột khác để so sánh.'}</span>`}
 function prod(){const maximum=Math.max(...S.prod.req_moi_gio);return controls()+`<div class="measure-grid"><div><span>Tổng trong cửa sổ đo</span><strong>${number(S.prod.tong_req_24h)}</strong><span>request / 24 giờ · đã đo</span></div><div><span>Giờ đông request nhất</span><strong>${S.prod.gio_dinh.gio}h</strong><span>${number(maximum)} request · đã đo</span></div></div><div id="hour-value" class="selected-hour" aria-live="polite"></div><div class="hours-chart" aria-label="Request theo từng giờ">${S.prod.req_moi_gio.map((v,h)=>`<button type="button" data-hour="${h}" aria-label="${h} giờ, ${number(v)} request" aria-pressed="${h===hour}"><i style="--bar:${Math.max(1,v/maximum*100)}%"></i></button>`).join('')}</div><div class="hours-labels" aria-hidden="true"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div><details><summary>Đọc toàn bộ 24 giá trị</summary><div class="table-scroll"><table><thead><tr><th>Giờ Việt Nam</th><th>Request đã đo</th></tr></thead><tbody>${S.prod.req_moi_gio.map((n,h)=>`<tr><td>${h}h</td><td>${number(n)}</td></tr>`).join('')}</tbody></table></div></details><div class="story-note"><strong>Số này nói được điều gì?</strong><p>Cho thấy giờ hệ thống nhận nhiều lượt gọi, gồm cả gọi tự động của các tab. Không dùng số request để suy ra số người đang bấm hoặc số bệnh nhân.</p></div>`+source('docs/he-thong/so-do.json → prod.req_moi_gio',`<p>Thời điểm đo: ${escape(S.do_luc)}</p><p>${escape(S.ghi_chu)}</p>`)}
 function tasks(){return `<div class="task-guide">${data.tasks.map(t=>`<details><summary><span class="task-number">${t.number}.</span><span>${escape(t.title)}<br><span class="tag ${t.high?'red':'yellow'}">${t.high?'Có phần mức 3 · cần duyệt trước khi sửa':'Mức 2 · đổi hành vi'}</span></span></summary><div class="task-body">${t.html}<a href="#lego/${escape(t.block)}">Xem khối liên quan →</a> · <a href="#viec-can-lam/${escape(t.anchor)}">Đọc trong kế hoạch đầy đủ →</a></div></details>`).join('')}</div><p style="margin-top:24px"><a href="#viec-can-lam">Mở cả 10 việc, 56 PR và kế hoạch 4 tuần →</a></p>`}
 function chapterView(){
  stop();step=0;elapsed=0;
  document.querySelectorAll('[data-chapter]').forEach(b=>{const active=b.dataset.chapter===chapter;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1});
  $('guide-panel').setAttribute('aria-labelledby','chapter-'+chapter);
  const list=chapter==='journey'?journey.map(x=>x.ten):chapter==='payment'?paymentTitles:['Ghi sự kiện','Nghỉ 1 giây','Giao lần lượt','Màn nhận tin'];
  const story=controls()+`<label class="mobile-step" for="story-select">Chọn bước để đọc<select id="story-select">${list.map((n,i)=>`<option value="${i}">${i+1}. ${escape(n)}</option>`).join('')}</select></label><div class="story-layout"><div class="story-steps" role="group" aria-label="Chọn bước">${list.map((n,i)=>`<button type="button" data-story-step="${i}"><span>${i+1}</span>${escape(n)}</button>`).join('')}</div><div><div id="story-detail" class="story-detail"></div>${pager()}</div></div>`;
  $('guide-panel').innerHTML=`<div class="guide-surface">${heading()}${chapter==='load'?load():chapter==='prod'?prod():chapter==='tasks'?tasks():story}</div>`;
  if(chapter==='load'){
   drawLoad();$('load-range').addEventListener('input',()=>{stop();people=Number($('load-range').value);drawLoad()});
   document.querySelectorAll('[data-people]').forEach(b=>b.onclick=()=>{stop();people=Number(b.dataset.people);$('load-range').value=people;drawLoad()});
  }else if(chapter==='prod'){
   drawChart();selectHour(hour);document.querySelectorAll('[data-hour]').forEach(b=>b.onclick=()=>selectHour(Number(b.dataset.hour)));
   // Vẽ dần đúng một lần khi biểu đồ được cuộn tới; giảm chuyển động giữ bản tĩnh.
   if(!reduced.matches){drawChart(0);const observer=new IntersectionObserver(entries=>{if(chapter==='prod'&&entries.some(e=>e.isIntersecting)){playing=true;$('guide-play').textContent='Tạm dừng';$('guide-play').setAttribute('aria-pressed','true');elapsed=0;schedule();observer.disconnect()}},{threshold:.4});observer.observe(document.querySelector('.hours-chart'));}
  }else if(chapter!=='tasks')drawStep();
  buttons();
  position();const i=chapterKeys.indexOf(chapter);$('chapter-counter').textContent=`${i+1} / 6`;$('chapter-prev').disabled=i===0;$('chapter-next').disabled=i===5;
 }
 function selectChapter(key){if(!chapterKeys.includes(key))key='journey';chapter=key;chapterView()}
 $('begin-guide').onclick=()=>{window.navigate('tong-quan','journey');$('guide-panel').scrollIntoView({block:'start'})};
 document.querySelectorAll('[data-chapter]').forEach(b=>{
  b.addEventListener('click',()=>{window.navigate('tong-quan',b.dataset.chapter);$('guide-panel').scrollIntoView({block:'start'})});
  b.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const index=chapterKeys.indexOf(chapter),next=(index+(e.key==='ArrowRight'?1:-1)+6)%6;window.navigate('tong-quan',chapterKeys[next]);document.querySelector('[data-chapter="'+chapterKeys[next]+'"]').focus()}});
 });
 $('chapter-prev').onclick=()=>window.navigate('tong-quan',chapterKeys[Math.max(0,chapterKeys.indexOf(chapter)-1)]);
 $('chapter-next').onclick=()=>window.navigate('tong-quan',chapterKeys[Math.min(5,chapterKeys.indexOf(chapter)+1)]);
 document.addEventListener('clinicai-route',e=>{if(e.detail.section==='tong-quan')selectChapter(e.detail.target.split('/')[0]||'journey');else stop()});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
 reduced.addEventListener('change',()=>{stop();chapterView()});
 selectChapter('journey');
})();

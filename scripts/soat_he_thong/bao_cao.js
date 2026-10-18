const CO_MAY = location.protocol.startsWith('http');
document.querySelectorAll('[data-quyet]').forEach(b=>{
  if(!CO_MAY){b.disabled=true;b.title='Mở báo cáo qua may_xem.py để ghi quyết định';return}
  b.onclick=async()=>{
    const id=b.closest('details').dataset.id;
    const ly=b.dataset.quyet==='chap_nhan'?'':prompt('Lý do (bắt buộc, 1 dòng):');
    if(b.dataset.quyet!=='chap_nhan'&&!ly)return;
    const r=await fetch('/duyet',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({id,quyet_dinh:b.dataset.quyet,ly_do:ly||''})});
    if(r.ok){b.closest('.nut').innerHTML='<span class=da>Đã ghi: '+b.dataset.quyet+'</span>'}
  }});

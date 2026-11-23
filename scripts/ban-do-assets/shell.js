(() => {
 'use strict';
 const $=id=>document.getElementById(id);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const normal=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();
 const saved=(key,fallback)=>{try{return localStorage.getItem(key)||fallback}catch(e){return fallback}};
 let theme=saved('ban-do-theme',matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
 let large=saved('ban-do-large','0')==='1',previous='';
 const state=target=>({clinicai:'state',theme,font:large?18:16,target:target||''});
 function sync(){
  document.documentElement.dataset.theme=theme;document.body.dataset.theme=theme;
  document.documentElement.style.setProperty('--reading',large?'18px':'16px');
  $('font').setAttribute('aria-pressed',String(large));
  $('theme').textContent=theme==='dark'?'Đổi sang sáng':'Đổi sang tối';
  document.querySelectorAll('iframe').forEach(f=>f.contentWindow.postMessage(state(),'*'));
 }
 $('theme').onclick=()=>{theme=theme==='light'?'dark':'light';try{localStorage.setItem('ban-do-theme',theme)}catch(e){}sync()};
 $('font').onclick=()=>{large=!large;try{localStorage.setItem('ban-do-large',large?'1':'0')}catch(e){}sync()};
 function menu(open){$('rail').classList.toggle('open',open);$('menu').setAttribute('aria-expanded',String(open))}
 $('menu').onclick=()=>menu(!$('rail').classList.contains('open'));
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){menu(false);$('global-results').hidden=true}});
 document.addEventListener('click',e=>{if(!e.target.closest('.rail,#menu'))menu(false);if(!e.target.closest('.search-wrap'))$('global-results').hidden=true});
 function createFrame(section){
  const host=document.querySelector('#'+section+' .frame-wrap');
  if(!host)return null;
  let frame=host.querySelector('iframe');
  if(!frame){frame=document.createElement('iframe');frame.title=sectionNames[section]+' — bản đồ đầy đủ';frame.setAttribute('sandbox','allow-scripts allow-same-origin');frame.srcdoc=frames[section];host.append(frame)}
  return frame;
 }
 window.navigate=function(section,target=''){
  const value=section+(target?'/'+target:'');
  if(location.hash.slice(1)===value)window.renderRoute();else location.hash=value;
 };
 window.renderRoute=function(){
  let hash;try{hash=decodeURI(location.hash.slice(1))}catch(e){hash='tong-quan'}
  const [key,...rest]=(hash||'tong-quan').split('/');const section=sectionNames[key]?key:'tong-quan',target=rest.join('/');
  document.querySelectorAll('main>section').forEach(el=>el.hidden=el.id!==section);
  document.querySelectorAll('#'+section+' [data-frame-target]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.frameTarget===target)));
  document.querySelectorAll('.rail nav a').forEach(a=>{if(a.hash==='#'+section)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  $('where').textContent=sectionNames[section];document.title=sectionNames[section]+' · Bản đồ ClinicAI';menu(false);
  if(section==='he-thong'||section==='so-hoc'){createFrame(section)?.contentWindow.postMessage(state(target),'*')}
  if(section==='lego'&&target.startsWith('goc/')){
   document.querySelector('#lego .original').open=true;
   createFrame('lego')?.contentWindow.postMessage(state(target.slice(4)),'*');
  }
  document.dispatchEvent(new CustomEvent('clinicai-route',{detail:{section,target}}));
  if(previous!==section){window.scrollTo(0,0);if(matchMedia('(max-width:1080px)').matches){const toc=document.querySelector('#'+section+' .doc-toc details');if(toc)toc.open=false}previous=section}
  if(['viec-can-lam','toc-do','muc-luc'].includes(section)&&target){
   const decoded=(()=>{try{return decodeURIComponent(target)}catch(e){return ''}})();
   document.getElementById(section+'-'+decoded)?.scrollIntoView({block:'start'});
  }
 };
 document.querySelector('.skip').addEventListener('click',e=>{e.preventDefault();document.getElementById('noi-dung').focus();document.getElementById('noi-dung').scrollIntoView({block:'start'})});
 window.addEventListener('hashchange',window.renderRoute);
 window.addEventListener('message',e=>{
  const data=e.data;if(!data?.clinicai)return;
  const frame=[...document.querySelectorAll('iframe')].find(f=>f.contentWindow===e.source);if(!frame)return;
  const section=frame.closest('main>section').id;
  if(data.clinicai==='navigate'){window.navigate(data.section,data.target||'');return}
  if(data.clinicai==='ready'){
   const current=location.hash.slice(1).split('/');let target=current[0]===section?current.slice(1).join('/'):'';
   if(section==='lego')target=target.startsWith('goc/')?target.slice(4):'';
   frame.contentWindow.postMessage(state(target),'*');return;
  }
  if(data.clinicai==='hash'&&!frame.closest('main>section').hidden){
   const prefix=section==='lego'?'goc/':'';
   history.replaceState(null,'','#'+section+'/'+prefix+(data.hash||''));
  }
 });
 document.querySelectorAll('.original').forEach(el=>el.addEventListener('toggle',()=>{if(el.open)createFrame(el.closest('section').id)}));
 document.querySelectorAll('[data-frame-target]').forEach(button=>button.addEventListener('click',()=>window.navigate(button.closest('section').id,button.dataset.frameTarget)));
 const data=window.MAP_DATA;
 const index=[
  ...data.lego.thao_tac.map(o=>({title:o.ten,type:'Thao tác',text:[o.man_ten,o.man,o.ai,o.api,JSON.stringify(o)].join(' '),section:'lego',target:'nv/'+o.id})),
  ...[...data.lego.khoi_nghiep_vu,...data.lego.khoi_ha_tang].map(k=>({title:k.ten,type:'Khối lego',text:JSON.stringify(k),section:'lego',target:k.id})),
  ...data.dictionary.map(k=>({title:k.ten,type:'Từ điển · '+k.loai,text:JSON.stringify(k),section:'so-hoc',target:'/tu-dien?q='+encodeURIComponent(k.code)})),
  ...Object.entries(sectionNames).map(([section,title])=>({title,type:'Mục',text:title,section,target:''}))
 ];
 index.forEach(item=>item.search=normal(item.title+' '+item.text));
 $('global-search').addEventListener('input',()=>{
  const query=normal($('global-search').value.trim());const box=$('global-results');box.hidden=!query;if(!query)return;
  const words=query.split(/\s+/),matches=index.filter(item=>words.every(w=>item.search.includes(w))).slice(0,12);
  box.innerHTML=matches.length?matches.map(item=>`<a href="#${item.section}${item.target?'/'+esc(item.target):''}"><small>${esc(item.type)}</small>${esc(item.title)}</a>`).join(''):'<p>Chưa tìm thấy. Thử “thu tiền”, “check-in” hoặc “payment”.</p>';
 });
 $('global-search').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('global-results').querySelector('a')?.click()}});
 $('global-results').addEventListener('click',e=>{if(e.target.closest('a')){$('global-results').hidden=true;$('global-search').blur()}});
 sync();
})();

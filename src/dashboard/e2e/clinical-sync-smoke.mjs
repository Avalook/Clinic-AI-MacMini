// Real form, two browser contexts, synthetic network fixtures; no clinic APIs.
import { mkdir, writeFile, rm } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const root=dirname(dirname(fileURLToPath(import.meta.url)));
// Temporary static-suffix route bypasses auth middleware; this tests UI only.
const name=`clinical-sync-qa-${Date.now()}.svg`, doctorName=`clinical-sync-doctor-${Date.now()}.svg`;
const route=join(root,'app',name), doctorRoute=join(root,'app',doctorName);
let child,browser,logs='';
try {
 await mkdir(route); await mkdir(doctorRoute);
 await writeFile(join(route,'page.tsx'),`"use client";
import ClinicalRecordForm from '../(dashboard)/tasks/ClinicalRecordForm';
const appt={id:'11111111-1111-4111-8111-111111111111',slot_start:'2026-09-15T01:00:00Z',status:'CHECKED_IN',patient:{clinic_patient_id:'22222222-2222-4222-8222-222222222222',patient_code:'QA',full_name:'QA Test',date_of_birth:null,phone_primary:null,phone_secondary:null,gender:'Nữ',ethnicity:null,nationality:null,occupation:null,patient_objection:null,address:null,guardian_name:null},service:{name:'Khám phụ khoa',form_code:'PK'}};
export default function QA(){return <ClinicalRecordForm appt={appt} staffId="qa" canSign={false} onClose={()=>{}}/>;}`);
 await writeFile(join(doctorRoute,'page.tsx'), (await (await import('node:fs/promises')).readFile(join(route,'page.tsx'),'utf8')).replace('canSign={false}','canSign={true}'));
 child=spawn(process.execPath,[join(root,'node_modules/next/dist/bin/next'),'dev','-p','13590'],{cwd:root,env:{...process.env,NEXT_TELEMETRY_DISABLED:'1'},stdio:['ignore','pipe','pipe']});
 child.stdout.on('data',d=>logs+=d);child.stderr.on('data',d=>logs+=d);
 for(let n=0;n<80;n++){if(logs.includes('Ready in'))break;if(child.exitCode!==null)throw Error(logs);await new Promise(r=>setTimeout(r,250));}
 assert.ok(logs.includes('Ready in'),logs);
 browser=await chromium.launch({headless:true, channel:process.env.CLINICAI_QA_BROWSER || "chrome"});
 let record={revision:1,profile:null,pregnancy:null,labs:[],history:[{visit_id:'55555555-5555-4555-8555-555555555555',created_at:'2026-08-15T01:00:00Z',status:'FINALIZED',service:'Khám cũ',doctor:'QA',chief_complaint:'Lượt cũ',assessment:'Cũ'}],prescriptions:[],prescription_draft:null,visit:{visit_id:'33333333-3333-4333-8333-333333333333',status:'IN_PROGRESS'},draft:{chief_complaint:'Ban đầu',subjective:{},objective:{vitals:{huyet_ap:'120/80',can_nang:'60',chieu_cao:'160'}},assessment:{chan_doan:'Đã khám'},plan:{loi_dan:'Đã dặn'}}};
 const posts=[],completionRequests=[],pages=[];
 for(let i=0;i<2;i++){
  const context=await browser.newContext();
  await context.route('**/api/**',async r=>{
   if(new URL(r.request().url()).pathname==='/api/clinical-record'){
    if(r.request().method()==='GET' && new URL(r.request().url()).searchParams.has('visitId')) return r.fulfill({json:{...record,visit:{visit_id:'55555555-5555-4555-8555-555555555555',status:'FINALIZED'},draft:{...record.draft,chief_complaint:'Lượt cũ'}}});
    if(r.request().method()==='POST'){const b=r.request().postDataJSON();posts.push(b);assert.equal(b.expectedRevision,record.revision);if(b.approvePrescriptionDraft){record={...record,prescription_draft:null,prescriptions:record.prescription_draft.items.map(x=>({id:'44444444-4444-4444-8444-444444444444',drug_name_raw:x.drug_name,quantity:x.quantity,dosage_instructions:x.dosage,caution:x.caution}))};}record={...record,revision:record.revision+1,draft:{chief_complaint:b.chief_complaint,subjective:b.subjective,objective:b.objective,assessment:b.assessment,plan:b.plan}};}
    return r.fulfill({json:record});
   }
   if(new URL(r.request().url()).pathname==='/api/appointments' && r.request().method()==='PATCH'){
    completionRequests.push(r.request().postDataJSON());return r.fulfill({json:{status:'COMPLETED'}});
   }
   return r.fulfill({json:{drugs:[],cls:[],state:'DRAFT',version:1,missing:[],can_sign:false,can_release:false,can_amend:false}});
  });
  const page=await context.newPage();pages.push(page);await page.goto(`http://localhost:13590/${i===1 ? doctorName : name}`);
  await page.getByRole('button',{name:/^Khám✓/}).click();await page.getByPlaceholder('VD: Khám thai').waitFor();
 }
 const [secretary,doctor]=pages;
 await secretary.getByPlaceholder('VD: Khám thai').fill('Thư ký đã nhập');
 await secretary.getByRole('button',{name:/Lưu hồ sơ/}).click();
 await secretary.waitForFunction(()=>document.body.textContent.includes('Đã lưu nháp'));
 await doctor.evaluate(()=>window.dispatchEvent(new CustomEvent('clinicai:bang-doi',{detail:'clinical_record'})));
 await doctor.waitForFunction(()=>document.querySelector('input[placeholder="VD: Khám thai"]')?.value==='Thư ký đã nhập');
 assert.equal(posts.length,1);
 await doctor.getByPlaceholder('VD: Khám thai').fill('Bác sĩ đang sửa');
 await doctor.getByRole('button',{name:'Kết thúc khám',exact:true}).click();
 await doctor.waitForFunction(()=>document.body.textContent.includes('Bạn còn nội dung chưa lưu'));
 assert.equal(completionRequests.length,0,'unsaved doctor typing cannot end the appointment');
 record={...record,revision:3,draft:{...record.draft,chief_complaint:'Bản mới của thư ký'}};
 await doctor.evaluate(()=>window.dispatchEvent(new CustomEvent('clinicai:bang-doi',{detail:'clinical_record'})));
 await doctor.getByRole('status').waitFor();
 assert.equal(await doctor.getByPlaceholder('VD: Khám thai').inputValue(),'Bác sĩ đang sửa');
 await doctor.getByRole('button',{name:'Tải bản mới và bỏ nội dung chưa lưu'}).click();
 await doctor.waitForFunction(()=>document.querySelector('input[placeholder="VD: Khám thai"]')?.value==='Bản mới của thư ký');
 record={...record,revision:4,prescription_draft:{recorded_by:'qa-secretary',items:[{drug_name:'QA Drug',quantity:'2 viên',dosage:'QA instructions',caution:''}]}};
 await doctor.evaluate(()=>window.dispatchEvent(new CustomEvent('clinicai:bang-doi',{detail:'clinical_record'})));
 await doctor.getByRole('button',{name:/^Chẩn đoán & Xử trí/}).click();
 await doctor.getByRole('button',{name:'Duyệt đơn thuốc đang xem'}).waitFor();
 await doctor.getByRole('button',{name:'Kết thúc khám',exact:true}).click();
 await doctor.waitForFunction(()=>document.body.textContent.includes('Còn đơn thuốc thư ký nhập chờ bác sĩ duyệt'));
 assert.equal(completionRequests.length,0,'pending prescription cannot end the appointment');
 await doctor.getByRole('button',{name:'Duyệt đơn thuốc đang xem'}).click();
 await doctor.waitForFunction(()=>document.body.textContent.includes('Đã duyệt đơn thuốc thư ký nhập'));
 assert.equal(posts.at(-1).approvePrescriptionDraft,true);
 assert.equal(posts.at(-1).expectedRevision,4);
 assert.equal(record.prescriptions[0].drug_name_raw,'QA Drug');
 await doctor.getByRole('button',{name:'Khám cũ',exact:true}).click();
 await doctor.waitForFunction(()=>document.querySelector('input[placeholder="VD: Khám thai"]')?.value==='Lượt cũ');
 await doctor.getByRole('button',{name:'Khám mới',exact:true}).click();
 await doctor.getByRole('button',{name:/^Khám✓/}).click();
 await doctor.waitForFunction(()=>document.querySelector('input[placeholder="VD: Khám thai"]')?.value==='Bản mới của thư ký');
 assert.equal(posts.length,2,'history navigation must not save anything');
 assert.equal(completionRequests.length,0,'saving and approval must not end the appointment');
 doctor.once('dialog',dialog=>dialog.accept());
 await doctor.getByRole('button',{name:'Kết thúc khám',exact:true}).click();
 await doctor.waitForFunction(()=>document.body.textContent.includes('Đã kết thúc khám'));
 assert.deepEqual(completionRequests,[{id:'11111111-1111-4111-8111-111111111111',action:'complete'}]);
 console.log('clinical sync UI smoke passed: two-role edit, dirty/pending end guards, prescription approval, explicit exam completion');
}catch(e){console.error(logs.slice(-2500));throw e;}
finally{if(browser)await browser.close();if(child&&child.exitCode===null){child.kill('SIGTERM');await new Promise(r=>child.once('exit',r));}await rm(route,{recursive:true,force:true});await rm(doctorRoute,{recursive:true,force:true});await rm(join(root,'.next','dev','types'),{recursive:true,force:true});}

/* Real main React component, synthetic HTTP responses, isolated headless browser.
 * No application server, credentials, external requests or production data.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const {createRequire} = require('module');
const dashboard = '/Users/quangdang/Projects/Dr4Women-MacMini/src/dashboard';
const main = '/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini/src/dashboard';
const req = createRequire(path.join(dashboard, 'package.json'));
const webpack = req('next/dist/compiled/webpack/webpack').webpack;
const {chromium} = req('playwright');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'clinicai-note-audit-'));
fs.writeFileSync(path.join(temp, 'loader.cjs'), `const ts=require(${JSON.stringify(req.resolve('typescript'))}); module.exports=function(source){return ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText;};`);
fs.writeFileSync(path.join(temp, 'entry.tsx'), `import React from 'react';import {createRoot} from 'react-dom/client';import GhiChuLuot from ${JSON.stringify(path.join(main, 'app/(dashboard)/_lam-viec/phieu-kham/GhiChuLuot.tsx'))};createRoot(document.getElementById('root')!).render(<GhiChuLuot visitId="00000000-0000-4000-8000-000000000001" choGhi={true}/>);`);

(async () => {
  await new Promise((resolve,reject) => webpack({mode:'development',target:'web',devtool:false,entry:path.join(temp,'entry.tsx'),output:{path:temp,filename:'bundle.js'},resolve:{extensions:['.tsx','.ts','.js'],alias:{'@':main},modules:[path.join(dashboard,'node_modules')]},module:{rules:[{test:/\.tsx?$/,use:path.join(temp,'loader.cjs')}]},optimization:{minimize:false}},(error,stats)=>error?reject(error):stats.hasErrors()?reject(new Error(stats.toString({all:false,errors:true}))):resolve()));
  const server = http.createServer((request,response)=>{
    if(request.url==='/bundle.js'){response.setHeader('Content-Type','text/javascript');response.end(fs.readFileSync(path.join(temp,'bundle.js')));}
    else {response.setHeader('Content-Type','text/html');response.end('<!doctype html><html><meta charset="utf-8"><div id="root"></div><script src="/bundle.js"></script></html>');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const page = await browser.newPage();
  const errors=[]; const writes=[]; let reads=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/ho-so-kham**',async route=>{
    if(route.request().method()==='PUT'){
      writes.push(route.request().postDataJSON());
      await route.fulfill({status:409,json:{detail:'Ghi chú vừa được người khác lưu — đã nạp bản mới, gõ tiếp trên đó.'}});
    } else {
      reads++;
      await route.fulfill({json:{hien:true,ghi_duoc:true,ban:{phien_ban:reads===1?1:2,noi_dung:reads===1?'Synthetic initial note':'Synthetic concurrent server note',ghi_luc:null,ghi_boi:'Synthetic colleague'}}});
    }
  });
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    const field=page.getByRole('textbox',{name:'Ghi chú',exact:true});
    await field.waitFor();
    await field.fill('Synthetic local observation that has never been saved');
    await field.blur();
    await page.waitForFunction(()=>document.querySelector('textarea')?.value==='Synthetic concurrent server note');
    const actual=await field.inputValue();
    const result={sha:'956ba4f236b1c92f1280d2097018c199e90ce8c7',method:'actual React component + real autosave hook + synthetic 409 HTTP contract in headless Chrome',reads,writes,localDraftRetained:actual.includes('local observation'),textareaAfterConflict:actual,pageErrors:errors,limitation:'Component-level browser reproduction; not a full application/backend concurrency test'};
    fs.writeFileSync(path.join(__dirname,'note-conflict-browser.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
    if(result.localDraftRetained || errors.length)throw new Error('Expected observation was not reproduced cleanly');
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));fs.rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});

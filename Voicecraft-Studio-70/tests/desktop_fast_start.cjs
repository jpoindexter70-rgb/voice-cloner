// Real renderer opens before a deliberately delayed real engine startup.
const {_electron}=require('playwright-core'),{spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs');
(async()=>{
 const origin=process.env.VOICECRAFT_TEST_ORIGIN||'http://127.0.0.1:8802';
 const args=[path.resolve(__dirname,'../desktop')];if(process.platform==='linux')args.unshift('--no-sandbox');
 let engine;const before=Date.now();
 const application=await _electron.launch({executablePath:process.env.ELECTRON_EXE,args,env:{...process.env,VOICECRAFT_DESKTOP_ORIGIN:origin}});
 try{
  const page=await application.firstWindow();page.on('pageerror',error=>console.log('PAGE_ERROR',String(error)));await page.waitForURL('**/startup.html');await page.getByRole('heading',{name:'Voicecraft Studio 70'}).waitFor();
  const visible=Date.now()-before;if(visible>5000)throw Error('Desktop startup took '+visible+' ms');
  console.log('VISIBLE_DESKTOP_BEFORE_ENGINE_MS',visible);
  await application.evaluate(({dialog})=>{dialog.showMessageBoxSync=()=>1});
  await page.waitForTimeout(3000);if(!page.url().endsWith('/startup.html'))throw Error('Connected to an unexpected engine');
  const log=fs.openSync('/tmp/voicecraft70-fast-engine.log','w');
  engine=spawn(process.env.PYTHON_EXE,[path.resolve(__dirname,'../scripts/desktop.py'),'--engine-process'],{cwd:path.resolve(__dirname,'..'),env:{...process.env,VOICECRAFT_ENGINE_PORT:new URL(origin).port},stdio:['ignore',log,log]});fs.closeSync(log);
  await page.waitForURL(origin+'/',{timeout:60000});await page.waitForFunction(()=>token!=='');
  await page.waitForFunction(()=>document.getElementById('short-preview').disabled);
  if(!(await page.evaluate(()=>api('/startup'))).ready)console.log('WORKSPACE_VISIBLE_WHILE_ENGINE_STARTS');else throw Error('Did not exercise pending engine state');
  await page.locator('#add-family').click();await page.locator('#name').fill('Synthetic fast startup QA');await page.getByRole('button',{name:'Save Profile',exact:true}).click();await page.waitForFunction(()=>profiles.length===1);
  await page.getByRole('button',{name:'Select Voice',exact:true}).click();await page.locator('#nav-workspace').click();await page.locator('#script').fill('Welcome to our channel. Let us tell a new story together.');
  const bytes=Array.from(fs.readFileSync(process.env.VOICECRAFT_TEST_REFERENCE));
  await page.evaluate(async bytes=>{const f=new FormData();f.append('file',new File([Uint8Array.from(bytes)],'Synthetic.wav',{type:'audio/wav'}));await api('/profiles/'+selected+'/references',{method:'POST',body:f});await refresh()},bytes);
  async function until(predicate,timeout){const deadline=Date.now()+timeout;while(Date.now()<deadline){if(await predicate())return;await page.waitForTimeout(100)}throw Error('Condition timed out');}
  await until(()=>page.evaluate(async()=>{const s=await api('/startup');if(s.failed)throw Error(s.message);return s.ready}),240000);
  await page.waitForTimeout(1000);console.log('READY_UI_STATE',await page.evaluate(()=>({startup:document.getElementById('startup-status')?.outerHTML,button:document.getElementById('short-preview').outerHTML})));
  await page.waitForFunction(()=>!document.getElementById('short-preview').disabled);
  const state=await page.evaluate(()=>api('/engine'));if(state.loaded!=='turbo')throw Error('Turbo was not preloaded');
  await page.locator('#short-preview').click();await until(()=>page.evaluate(async()=>{const jobs=await api('/jobs');if(jobs.some(j=>j.status==='failed'))throw Error(JSON.stringify(jobs));return jobs.some(j=>j.status==='completed')}),180000);
  const job=(await page.evaluate(()=>api('/jobs')))[0];if(!(job.result.seconds>0))throw Error('No generated preview');
  console.log('BACKGROUND_VERIFICATION_TURBO_PRELOAD_AND_REAL_PREVIEW_PASSED',job.result.seconds);
 }finally{
  await application.close();if(engine){engine.kill();await new Promise(resolve=>engine.once('exit',resolve));}
 }
})().catch(error=>{console.error(error);process.exitCode=1});

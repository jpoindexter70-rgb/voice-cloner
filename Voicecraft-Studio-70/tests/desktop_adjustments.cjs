// Full desktop checks for the requested expanded controls; isolated synthetic data only.
const {_electron}=require('playwright-core'),path=require('node:path'),fs=require('node:fs');
(async()=>{
 if(!process.env.ELECTRON_EXE||!process.env.VOICECRAFT_TEST_REFERENCE)throw Error('Set ELECTRON_EXE and a synthetic VOICECRAFT_TEST_REFERENCE');
 const origin=process.env.VOICECRAFT_TEST_ORIGIN||'http://127.0.0.1:8791';const args=[path.resolve(__dirname,'../desktop')];
 if(process.platform==='linux'&&process.env.VOICECRAFT_LINUX_QA_NO_SANDBOX==='1')args.unshift('--no-sandbox');
 const application=await _electron.launch({executablePath:process.env.ELECTRON_EXE,args,env:{...process.env,VOICECRAFT_DESKTOP_ORIGIN:origin}});
 try{
  const page=await application.firstWindow();const errors=[];page.on('pageerror',error=>errors.push(String(error)));
  await page.waitForURL(origin+'/');await page.waitForFunction(()=>token!=='');
  await application.evaluate(({dialog,clipboard})=>{dialog.showMessageBoxSync=()=>1;clipboard.writeText('Welcome to our channel. Today we are exploring a wonderful new story together.');});
  if(!await page.locator('.cover-art').isVisible()||!await page.locator('.studio-stats').isVisible())throw Error('Home dashboard/cover missing');
  if((await page.evaluate(()=>api('/profiles'))).length)throw Error('Use empty isolated QA profiles');
  await page.locator('#add-family').click();await page.locator('#name').fill('Synthetic adjustment QA');await page.getByRole('button',{name:'Save Profile',exact:true}).click();await page.waitForFunction(()=>profiles.length===1);
  await page.getByRole('button',{name:'Select Voice',exact:true}).click();const id=await page.evaluate(()=>selected);
  const bytes=Array.from(fs.readFileSync(process.env.VOICECRAFT_TEST_REFERENCE));
  await page.evaluate(async([id,bytes])=>{const form=new FormData();form.append('file',new File([Uint8Array.from(bytes)],'Synthetic.wav',{type:'audio/wav'}));await api('/profiles/'+id+'/references',{method:'POST',body:form});await refresh()},[id,bytes]);
  await page.locator('#nav-workspace').click();await page.locator('#script').focus();await page.keyboard.press('Control+V');if(!(await page.locator('#script').inputValue()).startsWith('Welcome'))throw Error('Paste failed');
  async function until(predicate,limit=30000){const end=Date.now()+limit;while(Date.now()<end){if(await predicate())return;await page.waitForTimeout(100)}throw Error('Condition timed out');}
  if(errors.length)throw Error(errors.join('\n'));await until(()=>page.locator('#voice-warmth').isEnabled());
  for(const [key,value] of Object.entries({warmth:3,brightness:-1,softness:25,clarity:20,noise:8,pause:.45,temperature:.7})){
   await page.locator('#voice-'+key).fill(String(value));await page.locator('#voice-'+key).dispatchEvent('change');
   await until(()=>page.evaluate(async([key,value])=>{const p=(await api('/profiles'))[0];return key==='noise'?p.settings.denoise&&p.settings.noise_strength===value:p.settings[key]===value},[key,value]));
  }
  if(!await page.locator('#voice-expression').isDisabled()||!await page.locator('#voice-similarity').isDisabled())throw Error('Unsupported Turbo controls enabled');
  async function preview(){const response=page.waitForResponse(r=>r.url().endsWith('/preview')&&r.request().method()==='POST');await page.locator('#short-preview').click();const received=await response;if(!received.ok())throw Error(await received.text());const job=await received.json();let result;
   await until(async()=>{result=(await page.evaluate(()=>api('/jobs'))).find(j=>j.id===job.id);return result&&!['running','queued'].includes(result.status)},180000);if(result.status!=='completed')throw Error(JSON.stringify(result));return result;}
  const turbo=await preview();if(turbo.result.settings.warmth!==3||turbo.result.settings.softness!==25||!turbo.result.settings.denoise)throw Error('Tone settings absent from real preview');
  console.log('REAL_TURBO_EXPANDED_CONTROLS_PREVIEW_OK',turbo.result.seconds);
  await page.locator('#workspace-engine').selectOption('expressive');await until(()=>page.locator('#voice-expression').isEnabled());
  for(const [key,value] of Object.entries({expression:.8,similarity:.7})){await page.locator('#voice-'+key).fill(String(value));await page.locator('#voice-'+key).dispatchEvent('change');await until(()=>page.evaluate(async([key,value])=>(await api('/profiles'))[0].settings[key]===value,[key,value]));}
  const original=await preview();if(original.result.engine!=='expressive'||original.result.settings.expression!==.8||original.result.settings.similarity!==.7)throw Error('Original controls not applied');
  console.log('REAL_ORIGINAL_EXPRESSIVENESS_REFERENCE_GUIDANCE_PREVIEW_OK',original.result.seconds);
  // Adjust a saved recording and save only a previewed copy.
  await page.getByRole('button',{name:'Edit Audio',exact:true}).first().click();await page.locator('#edit-warmth').fill('2');await page.locator('#edit-softness').fill('15');await page.locator('#preview-edit').click();await until(async()=>!await page.locator('#save-edit').isDisabled());await page.locator('#save-edit').click();await until(()=>page.evaluate(()=>profiles[0].recordings.length===2));
  // Unsaved import has the same tone controls and preview-before-save guard.
  await page.locator('#import-voice').click();await page.locator('#audio-file').setInputFiles(process.env.VOICECRAFT_TEST_REFERENCE);await page.waitForFunction(()=>pending!==null);await page.locator('#record-adjustments').click();await page.locator('#record-warmth').fill('2');await page.locator('#record-clarity').fill('25');await page.locator('#preview-record-adjustments').click();await until(async()=>!await page.locator('#save-record').isDisabled());await page.locator('#cancel-record').click();
  await page.reload();await page.waitForFunction(()=>token!==''&&profiles.length===1);await page.locator('#nav-workspace').click();await until(async()=>await page.locator('#voice-warmth').inputValue()==='3');
  await page.locator('#nav-library').click();if(!await page.locator('.cover-art').isVisible()||await page.locator('#stat-profiles').innerText()!=='1')throw Error('Dashboard/count not retained');
  await page.screenshot({path:'/tmp/voicecraft70-updated-dashboard.png',fullPage:true});await page.locator('#nav-workspace').click();await page.screenshot({path:'/tmp/voicecraft70-updated-controls.png',fullPage:true});
  if(errors.length)throw Error(errors.join('\n'));console.log('RECORDING_TONE_PREVIEW_EDIT_PERSISTENCE_HOME_DASHBOARD_OK');
 }finally{await application.close();}
})().catch(error=>{console.error(error);process.exitCode=1});

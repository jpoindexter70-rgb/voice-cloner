// Real local AI inference with an explicitly synthetic reference, not a family recording.
const {_electron}=require('playwright-core'),path=require('node:path'),fs=require('node:fs');
(async()=>{
 const origin=process.env.VOICECRAFT_TEST_ORIGIN||'http://127.0.0.1:8880';
 const args=[path.resolve(__dirname,'../desktop')];if(process.platform==='linux')args.unshift('--no-sandbox');
 const application=await _electron.launch({executablePath:process.env.ELECTRON_EXE,args,env:{...process.env,VOICECRAFT_DESKTOP_ORIGIN:origin}});
 try{
  const page=await application.firstWindow(),errors=[];page.on('pageerror',error=>errors.push(String(error)));await page.waitForURL(origin+'/');await page.waitForFunction(()=>token!=='');
  await application.evaluate(({dialog})=>{dialog.showMessageBoxSync=()=>1});
  async function until(check,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){if(await check())return;await page.waitForTimeout(100)}throw Error('Test condition timed out');}
  async function completed(job){let current;await until(async()=>{current=(await page.evaluate(()=>api('/jobs'))).find(j=>j.id===job.id);return current&&!['queued','running'].includes(current.status)},300000);if(current.status!=='completed'||!current.result)throw Error(JSON.stringify(current));return current;}
  if((await page.evaluate(()=>api('/profiles'))).length)throw Error('Use isolated empty QA profiles');
  await page.locator('#add-family').click();await page.locator('#name').fill('Synthetic natural-quality QA');await page.getByRole('button',{name:'Save Profile',exact:true}).click();await page.waitForFunction(()=>profiles.length===1);await page.getByRole('button',{name:'Select Voice',exact:true}).click();const id=await page.evaluate(()=>selected),base='/profiles/'+id;
  const bytes=Array.from(fs.readFileSync(process.env.VOICECRAFT_TEST_REFERENCE));await page.evaluate(async([base,bytes])=>{const f=new FormData();f.append('file',new File([Uint8Array.from(bytes)],'Synthetic reference.wav',{type:'audio/wav'}));await api(base+'/references',{method:'POST',body:f});await refresh()},[base,bytes]);
  if(await page.locator('#quality-mode').inputValue()!=='natural_studio')throw Error('New profile is not in Natural Studio mode');
  await page.locator('#script').fill('Why does a CPU need 32 GB? Voicecraft explains it.');await page.locator('#natural-quality-panel details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
  await page.locator('#pronunciation-corrections').fill('Voicecraft = voice craft');await page.locator('#pronunciation-corrections').dispatchEvent('change');await until(()=>page.evaluate(()=>profiles[0].settings.pronunciations.Voicecraft==='voice craft'));
  await page.locator('#prepare-natural-script').click();await until(async()=>(await page.locator('#prepared-script').inputValue()).includes('thirty two gigabytes'));if(!(await page.locator('#prepared-script').inputValue()).includes('voice craft'))throw Error('Pronunciation correction not applied');
  const beforeReference=await page.evaluate(()=>profiles[0].primary_reference);
  await page.locator('#suggest-reference').click();await until(()=>page.locator('#reference-sections option').count());await page.locator('#preview-clean-reference').click();await until(async()=>!await page.locator('#save-clean-reference').isDisabled());await page.locator('#save-clean-reference').click();await until(()=>page.evaluate(()=>profiles[0].recordings.length===2));
  if(await page.evaluate(()=>profiles[0].primary_reference)===beforeReference)throw Error('Clean reference was not selected');
  console.log('SCRIPT_NORMALIZATION_PRONUNCIATION_AND_REFERENCE_CLEANUP_PASSED');
  // Baseline and improved pipeline use the same selected engine and the same seed.
  const comparisonResponse=page.waitForResponse(r=>r.url().endsWith('/compare-quality')&&r.request().method()==='POST');await page.locator('#compare-natural').click();const comparisons=await(await comparisonResponse).json();const turbo=[];for(const job of comparisons)turbo.push(await completed(job));
  if(turbo[0].result.settings.quality_mode!=='standard'||turbo[1].result.settings.quality_mode!=='natural_studio')throw Error('Comparison did not preserve modes');
  console.log('REAL_TURBO_BASELINE_AND_NATURAL_COMPARISON',JSON.stringify(turbo.map(j=>({seconds:j.result.seconds,processing:j.result.processing_seconds}))));
  await page.locator('#natural-recommended').click();await until(()=>page.evaluate(()=>profiles[0].settings.engine==='expressive'&&profiles[0].settings.similarity===.35));
  const candidateResponse=page.waitForResponse(r=>r.url().endsWith('/candidates')&&r.request().method()==='POST');await page.locator('#generate-natural-takes').click();const candidates=await(await candidateResponse).json();const original=[];for(const job of candidates)original.push(await completed(job));
  if(original.some(j=>j.result.engine!=='expressive'||!j.result.can_regenerate))throw Error('Original natural candidates failed');
  console.log('REAL_ORIGINAL_NATURAL_CANDIDATES',JSON.stringify(original.map(j=>({seconds:j.result.seconds,processing:j.result.processing_seconds}))));
  const chosen=original[0];const regenerated=await page.evaluate(async([base,asset])=>api(base+'/generated/'+asset+'/regenerate-sentence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sentence:1})}),[base,chosen.id]);const regeneratedResult=await completed(regenerated);if(regeneratedResult.result.regenerated_sentence!==1)throw Error('Sentence regeneration failed');
  await page.evaluate(async()=>{await refresh();renderHistory(profiles[0])});if(!await page.getByRole('button',{name:'Regenerate Sentence',exact:true}).count())throw Error('No sentence regeneration UI');await page.getByRole('button',{name:'Regenerate Sentence',exact:true}).first().click();await page.locator('#regenerate-sentence-choice').waitFor({state:'visible'});await page.locator('#cancel-sentence-regeneration').click();
  for(const format of ['wav','mp3']){const result=await page.evaluate(async([base,id,format])=>{const r=await fetch('/api'+base+'/generated/'+id+'/export/'+format);return {status:r.status,bytes:(await r.arrayBuffer()).byteLength}},[base,chosen.id,format]);if(result.status!==200||result.bytes<1000)throw Error('Export '+format+' failed');}
  const output=process.env.VOICECRAFT_NATURAL_QA_REPORT||'/tmp/voicecraft-natural-inference-report.json';fs.writeFileSync(output,JSON.stringify({turbo:turbo.map(j=>j.result),original:original.map(j=>j.result),regenerated:regeneratedResult.result},null,2));
  await page.reload();await page.waitForFunction(()=>profiles.length===1&&token!=='');await page.locator('#nav-workspace').click();await until(async()=>(await page.locator('#pronunciation-corrections').inputValue()).includes('voice craft')&&await page.locator('#workspace-engine').inputValue()==='expressive'&&await page.locator('#voice-similarity').inputValue()==='0.35');await page.screenshot({path:'/tmp/voicecraft-natural-workspace.png',fullPage:true});
  if(errors.length)throw Error(errors.join('\n'));console.log('REAL_NATURAL_SENTENCE_REGENERATION_EXPORT_PERSISTENCE_AND_UI_PASSED');
 }finally{await application.close();}
})().catch(error=>{console.error(error);process.exitCode=1});

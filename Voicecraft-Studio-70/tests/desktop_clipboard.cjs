// Uses the real Electron clipboard and native keyboard editing roles.
const {_electron}=require('playwright-core');const path=require('node:path');
(async()=>{
 if(!process.env.ELECTRON_EXE)throw Error('Set ELECTRON_EXE to the verified renderer executable');
 const origin=process.env.VOICECRAFT_TEST_ORIGIN||'http://127.0.0.1:8791';
 const args=[path.resolve(__dirname,'../desktop')];
 if(process.platform==='linux'&&process.env.VOICECRAFT_LINUX_QA_NO_SANDBOX==='1')args.unshift('--no-sandbox');
 const application=await _electron.launch({executablePath:process.env.ELECTRON_EXE,args,env:{...process.env,VOICECRAFT_DESKTOP_ORIGIN:origin}});
 try{
  const page=await application.firstWindow();await page.waitForURL(origin+'/');await page.waitForFunction(()=>token!=='');
  await application.evaluate(({dialog})=>{dialog.showMessageBoxSync=()=>1});
  await page.locator('#nav-workspace').click();
  const roles=await application.evaluate(({Menu})=>Menu.getApplicationMenu().items[0].submenu.items.map(item=>item.role));
  for(const role of ['undo','redo','cut','copy','paste','selectall'])if(!roles.includes(role))throw Error('Missing editing role '+role);
  for(const text of ['Paste a narration script.','First line.\nSecond line: café, mañana, storytelling 🎙.']){
   await application.evaluate(({clipboard},value)=>clipboard.writeText(value),text);
   await page.locator('#script').fill('');await page.locator('#script').focus();await page.keyboard.press(process.platform==='darwin'?'Meta+V':'Control+V');
   if(await page.locator('#script').inputValue()!==text)throw Error('Native paste did not preserve text');
  }
  // Confirm the actual right-click path constructs an editable context menu.
  await application.evaluate(({Menu})=>{global.clipboardContextRoles=null;const popup=Menu.prototype.popup;Menu.prototype.popup=function(options){global.clipboardContextRoles=this.items.map(item=>item.role);return popup.call(this,options)};});
  await page.locator('#script').click({button:'right'});await page.waitForTimeout(250);
  const contextRoles=await application.evaluate(()=>global.clipboardContextRoles);if(!contextRoles?.includes('paste'))throw Error('No right-click Paste command');
  await page.keyboard.press('Escape');
  console.log('REAL_CLIPBOARD_PASTE_MULTILINE_UNICODE_AND_CONTEXT_MENU_PASSED');
 }finally{await application.close();}
})().catch(error=>{console.error(error);process.exitCode=1});

// Release test: isolated synthetic profiles only. See STANDALONE-VALIDATION.md.
const {_electron} = require('playwright-core');
const {spawn} = require('node:child_process');
const path = require('node:path');
(async()=>{
 if(!process.env.ELECTRON_EXE || !process.env.VOICECRAFT_TEST_REFERENCE || !process.env.PYTHON_EXE)throw Error('Set ELECTRON_EXE, VOICECRAFT_TEST_REFERENCE, PYTHON_EXE and use an empty QA data directory');
 const origin=process.env.VOICECRAFT_TEST_ORIGIN || 'http://127.0.0.1:8791';
 const cdp=process.env.VOICECRAFT_TEST_CDP_PORT || '9340';
 const target=process.env.VOICECRAFT_TEST_EXPORT || path.join(require('node:os').tmpdir(),'voicecraft70-test-export.mp3');
 const args=['--use-fake-device-for-media-stream','--remote-debugging-port='+cdp,path.resolve(__dirname,'../desktop')];
 if(process.env.VOICECRAFT_LINUX_QA_NO_SANDBOX==='1' && process.platform==='linux')args.unshift('--no-sandbox');
 const application=await _electron.launch({executablePath:process.env.ELECTRON_EXE,args,env:{...process.env,VOICECRAFT_DESKTOP_ORIGIN:origin}});
 try{
  const page=await application.firstWindow();await page.waitForURL(origin+'/');
  // The scripted Save As response avoids overwriting arbitrary user files.
  await application.evaluate(({dialog},destination)=>{dialog.showSaveDialogSync=()=>destination;dialog.showMessageBoxSync=()=>1;},target);
  const preferences=await application.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences());
  if(preferences.nodeIntegration || !preferences.sandbox || !preferences.contextIsolation)throw Error('Desktop isolation settings failed');
  console.log('DESKTOP_WINDOW_ISOLATION_OK');
  const processQA=spawn(process.env.PYTHON_EXE,[path.join(__dirname,'browser_voicecraft.py')],{env:{...process.env,VOICECRAFT_DESKTOP_CDP:'http://127.0.0.1:'+cdp,VOICECRAFT_TEST_ORIGIN:origin,VOICECRAFT_TEST_EXPORT:target},stdio:'inherit'});
  const result=await new Promise(resolve=>processQA.on('exit',resolve));if(result)throw Error('Voice workflow failed: '+result);
  await page.evaluate(()=>window.open('https://example.com'));await page.waitForTimeout(300);if(application.windows().length!==1)throw Error('New window unexpectedly allowed');
  await page.evaluate(()=>{location.href='https://example.com'});await page.waitForTimeout(300);if(!page.url().startsWith(origin))throw Error('External navigation unexpectedly allowed');
  console.log('DESKTOP_NAVIGATION_AND_EXPORT_OK');
  // Canceling close keeps the app alive; confirming it closes the actual window.
  await application.evaluate(({dialog,BrowserWindow})=>{dialog.showMessageBoxSync=()=>0;BrowserWindow.getAllWindows()[0].close();});
  if(application.windows().length!==1)throw Error('Cancel close did not retain window');
  await application.evaluate(({dialog})=>{dialog.showMessageBoxSync=()=>1;});
  console.log('DESKTOP_CLOSE_CONFIRMATION_OK');
 }finally{await application.close();}
 console.log('DESKTOP_CLOSE_OK');
})().catch(error=>{console.error(error);process.exitCode=1;});

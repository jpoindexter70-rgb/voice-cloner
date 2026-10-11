'use strict';
const {app, BrowserWindow, session, dialog, Menu} = require('electron');
const path = require('node:path');
const http = require('node:http');
const ORIGIN = process.env.VOICECRAFT_DESKTOP_ORIGIN || 'http://127.0.0.1:8791';
const url = new URL(ORIGIN);
if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.pathname !== '/') throw new Error('Only the local engine is permitted');
app.setName('Voicecraft Studio 70');
app.setPath('userData', path.join(app.getPath('appData'), 'Voicecraft-Studio-70'));
let window;
if (!app.requestSingleInstanceLock()) { app.quit(); }
else {
  app.on('second-instance', () => { if(window) {if(window.isMinimized())window.restore();window.show();window.focus();} });
  app.whenReady().then(() => {
    const local = value => {try{return new URL(value).origin === url.origin;}catch{return false;}};
    const ses = session.fromPartition('persist:voicecraft70');
    ses.setPermissionCheckHandler((_contents, permission, origin) => permission === 'media' && local(origin));
    ses.setPermissionRequestHandler((contents, permission, answer, details) => {
      // Microphone access belongs only to our local UI. Camera and unrelated permissions stay denied.
      answer(permission === 'media' && local(contents.getURL()) && local(details.requestingUrl || contents.getURL()) && (!details.mediaTypes || details.mediaTypes.every(type => type === 'audio')));
    });
    ses.on('will-download', (_event, item) => {
      const target = dialog.showSaveDialogSync(window, {title:'Export from Voicecraft Studio 70',defaultPath:path.join(app.getPath('downloads'),path.basename(item.getFilename())),buttonLabel:'Save'});
      if(!target){item.cancel();return;}
      item.setSavePath(target);
      item.once('done', (_event,state) => {if(state !== 'completed' && state !== 'cancelled')dialog.showErrorBox('Export failed','The audio could not be saved. Please try exporting again.');});
    });
    window = new BrowserWindow({title:'Voicecraft Studio 70',width:1440,height:960,minWidth:820,minHeight:600,backgroundColor:'#151719',autoHideMenuBar:true,icon:path.join(__dirname,'voicecraft.ico'),webPreferences:{partition:'persist:voicecraft70',nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false}});
    Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'Edit',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]}]));
    window.webContents.on('context-menu', (_event, params) => {
      if(params.isEditable)Menu.buildFromTemplate([{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]).popup({window});
    });
    window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
    window.webContents.on('will-navigate',(event,target)=>{if(!local(target))event.preventDefault();});
    window.webContents.on('will-redirect',(event,target)=>{if(!local(target))event.preventDefault();});
    window.webContents.on('did-fail-load',(_event,code,description,_url,isMainFrame)=>{if(isMainFrame && code !== -3)dialog.showErrorBox('Local engine unavailable',description+'\nClose and reopen Voicecraft Studio 70 to retry.');});
    window.on('close', event => {
      if (window.isDestroyed()) return;
      // Closing ends the engine, so let the user keep unfinished work running.
      if(dialog.showMessageBoxSync(window,{type:'question',title:'Close Voicecraft Studio 70?',message:'Close the app and stop its local AI engine?',detail:'Save or export any work first. A running generation will be interrupted.',buttons:['Keep open','Close app'],defaultId:0,cancelId:0})!==1)event.preventDefault();
    });
    window.loadFile(path.join(__dirname,'startup.html')).then(() => {
      const connect=()=>{
        if(window.isDestroyed())return;
        const request=http.get(ORIGIN+'/',response=>{
          response.resume();
          if(window.isDestroyed())return;
          if(response.statusCode===200){window.loadURL(ORIGIN);return;}
          setTimeout(connect,250);
        });
        request.setTimeout(1000,()=>request.destroy());
        request.on('error',()=>{if(!window.isDestroyed())setTimeout(connect,250)});
      };
      connect();
    });
  }).catch(error=>{dialog.showErrorBox('Desktop startup failed',String(error));app.exit(1);});
  app.on('window-all-closed',()=>app.quit());
}
